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
  signingKey = privateKey,
}: {
  email?: string | null;
  issuer?: string;
  audience?: string;
  expiresAt?: number;
  signingKey?: CryptoKey;
} = {}): Promise<string> {
  const claims = email === null ? {} : { email };
  return new SignJWT(claims)
    .setProtectedHeader({ alg: "RS256", kid: "test" })
    .setIssuer(issuer)
    .setAudience(audience)
    .setIssuedAt()
    .setExpirationTime(expiresAt)
    .sign(signingKey);
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
        await token({ expiresAt: Math.floor(Date.now() / 1000) - 1 }),
        TEAM_DOMAIN,
        AUDIENCE,
        getKey,
      ),
    ).rejects.toThrow();
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
