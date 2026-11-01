import { bindings, defineConfig, exports } from "cf/config";

export default defineConfig({
	worker: {
		name: "usr-memories",
		compatibilityDate: "2026-10-30",
		entrypoint: "src/index.ts",
		workersDev: false,
		previewUrls: false,
		domains: [
			"memories.17166969.xyz",
		],
		env: {
			DB: bindings.d1({
				name: "usr-memories",
				id: "00000000-0000-0000-0000-000000000000",
			}),
			BUCKET: bindings.r2({
				name: "usr-memories",
			}),
		},
		exports: {
			default: exports.worker({
				cache: {
					enabled: false,
				},
			}),
		},
	},
});
