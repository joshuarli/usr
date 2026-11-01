export interface AccessIdentity {
  readonly email: string | undefined;
  readonly service_token_id: string | undefined;
}

export type Principal = {
  readonly kind: "reader";
  readonly email: string;
};

function normalize(email: string): string {
  return email.trim().toLowerCase();
}

export function parseReaders(value: string | undefined): ReadonlySet<string> {
  if (value === undefined) return new Set();
  const readers = new Set<string>();
  for (const email of value.split(",")) {
    const normalized = normalize(email);
    if (normalized !== "") readers.add(normalized);
  }
  return readers;
}

export async function identityOf(context: ExecutionContext): Promise<AccessIdentity | null> {
  if (context === null || context === undefined) return null;
  const access = context.access;
  if (access === undefined) return null;
  try {
    const identity = await access.getIdentity();
    if (identity === undefined) return null;
    return {
      email: typeof identity.email === "string" ? identity.email : undefined,
      service_token_id: typeof identity.service_token_id === "string" ? identity.service_token_id : undefined,
    };
  } catch {
    return null;
  }
}

export function authorize(identity: AccessIdentity | null, readers: ReadonlySet<string>): Principal | null {
  if (identity === null) return null;
  if (identity.service_token_id !== undefined) return null;
  const email = identity.email;
  if (email === undefined) return null;
  const normalized = normalize(email);
  if (!readers.has(normalized)) return null;
  return { kind: "reader", email: normalized };
}
