import type { Component, TUI } from "@earendil-works/pi-tui";
import { truncateToWidth, visibleWidth, wrapTextWithAnsi } from "@earendil-works/pi-tui";
import type { KeybindingsManager, Theme } from "@earendil-works/pi-coding-agent";
import type { IntercomClient } from "../broker/client.ts";
import type { SessionInfo } from "../types.ts";
import { sanitizeDisplayText } from "./session-identity.ts";

export interface ComposeResult {
  sent: boolean;
  messageId?: string;
  text?: string;
}

export class ComposeOverlay implements Component {
  private tui: TUI;
  private theme: Theme;
  private keybindings: KeybindingsManager;
  private target: SessionInfo;
  private targetLabel: string;
  private client: IntercomClient;
  private done: (result: ComposeResult) => void;
  private inputBuffer: string = "";
  private pasteBuffer: string | null = null;
  private sending: boolean = false;
  private error: string | null = null;

  constructor(
    tui: TUI,
    theme: Theme,
    keybindings: KeybindingsManager,
    target: SessionInfo,
    targetLabel: string,
    client: IntercomClient,
    done: (result: ComposeResult) => void,
  ) {
    this.tui = tui;
    this.theme = theme;
    this.keybindings = keybindings;
    this.target = target;
    this.targetLabel = targetLabel;
    this.client = client;
    this.done = done;
  }

  invalidate(): void {}

  handleInput(data: string): void {
    if (this.sending) return;

    if (this.pasteBuffer !== null) {
      this.consumePaste(data);
      return;
    }

    const pasteStart = data.indexOf("\x1b[200~");
    if (pasteStart !== -1) {
      const beforePaste = data.slice(0, pasteStart);
      if (beforePaste) this.insertPrintable(beforePaste);
      this.pasteBuffer = "";
      this.consumePaste(data.slice(pasteStart + 6));
      return;
    }

    if (this.keybindings.matches(data, "tui.select.cancel")) {
      this.done({ sent: false });
      return;
    }

    if (this.keybindings.matches(data, "tui.input.newLine")) {
      this.inputBuffer += "\n";
      this.tui.requestRender();
      return;
    }

    if (
      this.keybindings.matches(data, "tui.input.submit")
      || this.keybindings.matches(data, "tui.select.confirm")
    ) {
      if (this.inputBuffer.trim()) {
        this.sendMessage();
      }
      return;
    }

    if (this.keybindings.matches(data, "tui.editor.deleteCharBackward")) {
      this.inputBuffer = [...this.inputBuffer].slice(0, -1).join("");
      this.tui.requestRender();
      return;
    }

    if (data.startsWith("\x1b")) return;
    this.insertPrintable(data);
  }

  private consumePaste(data: string): void {
    if (this.pasteBuffer === null) return;
    const pasteEnd = data.indexOf("\x1b[201~");
    if (pasteEnd === -1) {
      this.pasteBuffer += data;
      return;
    }

    const pastedText = this.pasteBuffer + data.slice(0, pasteEnd);
    this.pasteBuffer = null;
    this.inputBuffer += this.normalizeInput(pastedText, true);
    this.tui.requestRender();

    const remaining = data.slice(pasteEnd + 6);
    if (remaining) this.handleInput(remaining);
  }

  private normalizeInput(data: string, preserveNewlines = false): string {
    return data
      .replace(/\r\n?/g, "\n")
      .replace(/\t/g, "    ")
      .split("")
      .filter(character => {
        if (preserveNewlines && character === "\n") return true;
        const code = character.charCodeAt(0);
        return code >= 32 && code !== 127 && !(code >= 128 && code <= 159);
      })
      .join("");
  }

  private insertPrintable(data: string): void {
    const printable = this.normalizeInput(data);
    if (!printable) return;
    this.inputBuffer += printable;
    this.tui.requestRender();
  }

  private async sendMessage(): Promise<void> {
    this.sending = true;
    this.error = null;
    this.tui.requestRender();

    try {
      const result = await this.client.send(this.target.id, {
        text: this.inputBuffer.trim(),
      });

      if (!result.delivered) {
        this.error = sanitizeDisplayText(
          result.reason,
          "Message not delivered. Session may not exist or has disconnected.",
        );
        this.sending = false;
        this.tui.requestRender();
        return;
      }

      this.done({
        sent: true,
        messageId: result.id,
        text: this.inputBuffer.trim(),
      });
    } catch (error) {
      this.error = sanitizeDisplayText(error instanceof Error ? error.message : String(error), "Message failed");
      this.sending = false;
      this.tui.requestRender();
    }
  }

  render(width: number): string[] {
    const innerWidth = Math.max(1, Math.min(width, 72));
    if (innerWidth === 1) {
      return [this.theme.fg("accent", "│")];
    }

    const contentWidth = Math.max(0, innerWidth - 2);
    const sendKeys = this.keybindings.getKeys("tui.input.submit");
    const newlineKeys = this.keybindings.getKeys("tui.input.newLine");
    const footer = `${sendKeys.join("/")}: Send • ${newlineKeys.join("/")}: New line • ${this.keybindings.getKeys("tui.select.cancel").join("/")}: Close`;
    const border = (text: string) => this.theme.fg("accent", text);
    const row = (text = "") => {
      const clipped = truncateToWidth(text, contentWidth, "", true);
      return `${border("│")}${clipped}${" ".repeat(Math.max(0, contentWidth - visibleWidth(clipped)))}${border("│")}`;
    };

    const lines: string[] = [];
    const targetLabel = sanitizeDisplayText(
      this.targetLabel,
      sanitizeDisplayText(this.target.id, "Unknown session"),
    );
    const targetCwd = sanitizeDisplayText(this.target.cwd, "Unknown path");
    const targetModel = sanitizeDisplayText(this.target.model, "Unknown model");
    lines.push(border(`╭${"─".repeat(contentWidth)}╮`));
    lines.push(row(this.theme.bold(` Send to: ${targetLabel}`)));
    lines.push(row(this.theme.fg("dim", ` ${targetCwd} • ${targetModel}`)));
    lines.push(border(`├${"─".repeat(contentWidth)}┤`));
    lines.push(row());

    if (this.sending) {
      lines.push(row(this.theme.fg("dim", " Sending...")));
    } else if (this.error) {
      lines.push(row(this.theme.fg("error", ` Error: ${this.error}`)));
      lines.push(row());
      lines.push(...this.renderInputRows(contentWidth, row));
    } else {
      lines.push(...this.renderInputRows(contentWidth, row));
    }

    lines.push(row());
    lines.push(border(`├${"─".repeat(contentWidth)}┤`));
    lines.push(row(this.theme.fg("dim", ` ${footer}`)));
    lines.push(border(`╰${"─".repeat(contentWidth)}╯`));

    return lines;
  }

  private renderInputRows(contentWidth: number, row: (text?: string) => string): string[] {
    const promptWidth = Math.min(3, contentWidth);
    const textWidth = Math.max(1, contentWidth - promptWidth);
    const logicalLines = this.inputBuffer.split("\n");
    const rendered: string[] = [];

    logicalLines.forEach((logicalLine, logicalIndex) => {
      const wrapped = wrapTextWithAnsi(logicalLine, textWidth);
      const visualLines = wrapped.length ? wrapped : [""];
      visualLines.forEach((visualLine, visualIndex) => {
        const isFirst = logicalIndex === 0 && visualIndex === 0;
        const isLast = logicalIndex === logicalLines.length - 1 && visualIndex === visualLines.length - 1;
        rendered.push(row(`${isFirst ? " > " : "   "}${visualLine}${isLast ? "█" : ""}`));
      });
    });

    return rendered.slice(-8);
  }
}
