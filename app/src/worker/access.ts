import type { MiddlewareHandler } from "hono";
import { createRemoteJWKSet, jwtVerify, type JWTVerifyGetKey } from "jose";

export type AppEnv = {
  Bindings: Env;
  Variables: { userEmail: string };
};

const jwksByTeamDomain = new Map<string, JWTVerifyGetKey>();

/** Reuses jose's in-memory key cache while still refreshing rotated keys. */
function remoteJwks(teamDomain: string): JWTVerifyGetKey {
  let jwks = jwksByTeamDomain.get(teamDomain);
  if (!jwks) {
    jwks = createRemoteJWKSet(new URL(`${teamDomain}/cdn-cgi/access/certs`));
    jwksByTeamDomain.set(teamDomain, jwks);
  }
  return jwks;
}

/** Validates an Access application token and returns its authoritative email. */
export async function verifyAccessJwt(
  token: string,
  teamDomain: string,
  audience: string,
  getKey: JWTVerifyGetKey = remoteJwks(teamDomain),
): Promise<string> {
  const { payload } = await jwtVerify(token, getKey, {
    algorithms: ["RS256"],
    issuer: teamDomain,
    audience,
  });

  if (typeof payload.email !== "string" || payload.email.trim() === "") {
    throw new Error("Access JWT has no email claim");
  }
  return payload.email;
}

/** Authenticates API requests; local Vite development deliberately stays anonymous. */
export const accessAuth: MiddlewareHandler<AppEnv> = async (c, next) => {
  if (import.meta.env.DEV) {
    c.set("userEmail", "anonymous");
    await next();
    return;
  }

  if (!c.env.TEAM_DOMAIN || !c.env.POLICY_AUD) {
    console.error(
      JSON.stringify({ message: "Cloudflare Access bindings are missing" }),
    );
    return c.text("Forbidden", 403);
  }

  const token = c.req.header("Cf-Access-Jwt-Assertion");
  if (!token) return c.text("Forbidden", 403);

  try {
    c.set(
      "userEmail",
      await verifyAccessJwt(token, c.env.TEAM_DOMAIN, c.env.POLICY_AUD),
    );
  } catch (error) {
    console.warn(
      JSON.stringify({
        message: "Cloudflare Access JWT rejected",
        error: error instanceof Error ? error.message : "Unknown error",
      }),
    );
    return c.text("Forbidden", 403);
  }

  await next();
};
