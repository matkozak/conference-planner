import type { MiddlewareHandler } from "hono";
import {
  createRemoteJWKSet,
  errors,
  jwtVerify,
  type JWTVerifyGetKey,
} from "jose";

export type AppEnv = {
  Bindings: Env;
  Variables: { userEmail: string };
};

/** One team domain per deployment, so one cached JWKS (jose refreshes rotated keys). */
let jwks: JWTVerifyGetKey | undefined;

function remoteJwks(teamDomain: string): JWTVerifyGetKey {
  jwks ??= createRemoteJWKSet(new URL("/cdn-cgi/access/certs", teamDomain));
  return jwks;
}

/**
 * Validates an Access application token and returns its authoritative email.
 * Tokens without an email claim are rejected — that includes Access service
 * tokens (they authenticate as common_name); every caller of this app is a
 * person with an identity-provider login.
 */
export async function verifyAccessJwt(
  token: string,
  teamDomain: string,
  audience: string,
  getKey?: JWTVerifyGetKey,
): Promise<string> {
  // jose skips any claim check whose option is falsy, so a missing/empty
  // binding would silently accept tokens minted for other Access apps.
  // TypeError lands in the isJwksOutage branch: misconfiguration is a 503.
  if (!teamDomain || !audience) {
    throw new TypeError("TEAM_DOMAIN and POLICY_AUD must be non-empty");
  }
  // Access mints `iss` without a trailing slash; tolerate one in the binding.
  const issuer = teamDomain.replace(/\/+$/, "");
  const { payload } = await jwtVerify(token, getKey ?? remoteJwks(issuer), {
    algorithms: ["RS256"],
    issuer,
    audience,
    clockTolerance: 5, // seconds — Access sets nbf, and clocks can skew
  });

  if (typeof payload.email !== "string" || payload.email.trim() === "") {
    throw new Error("Access JWT has no email claim");
  }
  return payload.email;
}

/** The JWKS was unreachable or unusable — our outage, not the caller's token. */
function isJwksOutage(error: unknown): boolean {
  return (
    error instanceof TypeError || // fetch network failure or missing bindings
    error instanceof errors.JWKSTimeout ||
    error instanceof errors.JWKSInvalid ||
    // jose throws a bare JOSEError for a non-200 JWKS response
    (error instanceof errors.JOSEError &&
      error.constructor === errors.JOSEError)
  );
}

/** Authenticates API requests; local Vite development deliberately stays anonymous. */
export const accessAuth: MiddlewareHandler<AppEnv> = async (c, next) => {
  // DEV is a Vite build-time flag: false under `vite build` (the deploy path),
  // undefined outside Vite entirely — both fail closed into full validation.
  if (import.meta.env?.DEV) {
    c.set("userEmail", "anonymous");
    await next();
    return;
  }

  const token = c.req.header("Cf-Access-Jwt-Assertion");
  if (!token) return c.text("Forbidden", 403);

  try {
    c.set(
      "userEmail",
      await verifyAccessJwt(token, c.env.TEAM_DOMAIN, c.env.POLICY_AUD),
    );
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    if (isJwksOutage(error)) {
      console.error("Access JWKS unavailable:", reason);
      return c.text("Service Unavailable", 503);
    }
    console.warn("Access JWT rejected:", reason);
    return c.text("Forbidden", 403);
  }

  await next();
};
