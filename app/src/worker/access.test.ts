import {
  generateKeyPair,
  SignJWT,
  type CryptoKey,
  type JWTVerifyGetKey,
} from "jose";
import { beforeAll, describe, expect, it } from "vitest";
import { verifyAccessJwt } from "./access";

const TEAM_DOMAIN = "https://example.cloudflareaccess.com";
const AUDIENCE = "test-audience";
const EMAIL = "ada@example.com";

let privateKey: CryptoKey;
let otherPrivateKey: CryptoKey;
let getKey: JWTVerifyGetKey;

beforeAll(async () => {
  const primary = await generateKeyPair("RS256");
  const other = await generateKeyPair("RS256");
  privateKey = primary.privateKey;
  otherPrivateKey = other.privateKey;
  getKey = async () => primary.publicKey;
});

async function token({
  email = EMAIL,
  issuer = TEAM_DOMAIN,
  audience = AUDIENCE,
  expiresAt = Math.floor(Date.now() / 1000) + 300,
  notBefore,
  signingKey = privateKey,
}: {
  email?: string | null;
  issuer?: string;
  audience?: string;
  expiresAt?: number;
  notBefore?: number;
  signingKey?: CryptoKey;
} = {}): Promise<string> {
  const claims = email === null ? {} : { email };
  const jwt = new SignJWT(claims)
    .setProtectedHeader({ alg: "RS256", kid: "test" })
    .setIssuer(issuer)
    .setAudience(audience)
    .setIssuedAt()
    .setExpirationTime(expiresAt);
  if (notBefore !== undefined) jwt.setNotBefore(notBefore);
  return jwt.sign(signingKey);
}

describe("verifyAccessJwt", () => {
  it("returns the email from a valid Access token", async () => {
    await expect(
      verifyAccessJwt(await token(), TEAM_DOMAIN, AUDIENCE, getKey),
    ).resolves.toBe(EMAIL);
  });

  it.each([
    ["issuer", () => token({ issuer: "https://other.cloudflareaccess.com" })],
    ["audience", () => token({ audience: "other-audience" })],
    ["signature", () => token({ signingKey: otherPrivateKey })],
  ] as const)("rejects the wrong %s", async (_, makeToken) => {
    await expect(
      verifyAccessJwt(await makeToken(), TEAM_DOMAIN, AUDIENCE, getKey),
    ).rejects.toThrow();
  });

  it("rejects an expired token", async () => {
    await expect(
      verifyAccessJwt(
        // Beyond the 5s clockTolerance window
        await token({ expiresAt: Math.floor(Date.now() / 1000) - 60 }),
        TEAM_DOMAIN,
        AUDIENCE,
        getKey,
      ),
    ).rejects.toThrow();
  });

  it("tolerates a trailing slash on the team domain binding", async () => {
    await expect(
      verifyAccessJwt(await token(), `${TEAM_DOMAIN}/`, AUDIENCE, getKey),
    ).resolves.toBe(EMAIL);
  });

  it("tolerates small clock skew on a just-minted token", async () => {
    await expect(
      verifyAccessJwt(
        await token({ notBefore: Math.floor(Date.now() / 1000) + 3 }),
        TEAM_DOMAIN,
        AUDIENCE,
        getKey,
      ),
    ).resolves.toBe(EMAIL);
  });

  // A falsy audience/issuer makes jose skip that claim check entirely, so
  // missing bindings must hard-fail instead of silently widening acceptance.
  it.each([
    ["empty audience", () => verifyAccessJwt("x", TEAM_DOMAIN, "", getKey)],
    ["empty team domain", () => verifyAccessJwt("x", "", AUDIENCE, getKey)],
  ] as const)("rejects verification with an %s binding", async (_, verify) => {
    await expect(verify()).rejects.toThrow(TypeError);
  });

  it("rejects a token without an email", async () => {
    await expect(
      verifyAccessJwt(
        await token({ email: null }),
        TEAM_DOMAIN,
        AUDIENCE,
        getKey,
      ),
    ).rejects.toThrow("Access JWT has no email claim");
  });
});
