const headers = {
	"content-type": "text/x-sh; charset=utf-8",
	"cache-control": "no-cache",
};

export default {
	fetch(request, env): Response {
		if (new URL(request.url).pathname !== "/setup.sh") {
			return new Response("not found", { status: 404 });
		}
		if (request.method === "HEAD") {
			return new Response(null, { headers });
		}
		if (request.method !== "GET") {
			return new Response("method not allowed", { status: 405 });
		}
		return new Response(env.SETUP_SH, { headers });
	},
} satisfies ExportedHandler<{ SETUP_SH: string }>;
