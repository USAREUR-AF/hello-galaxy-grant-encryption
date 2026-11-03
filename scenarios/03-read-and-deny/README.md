# 03 — Read and deny

The whole apparatus runs end to end over a pub/sub bus: a member opens the stream, and an outsider handed the identical bytes cannot — because the read cut lives in the crypto, not the router.

## The problem

On a brokerless fabric there is no central gatekeeper deciding who receives which message; the router forwards bytes to whoever subscribes. So "who is allowed to read this stream" cannot be a router-side ACL you trust to hold the line. You need the access decision to survive even when the transport faithfully delivers the ciphertext to someone who should not be able to read it — including a fully enrolled peer who simply is not in the audience.

## What you'll see

1. The data owner grants the stream to org `northwind`; the key service derives the audience and publishes the signed bundle to its members.
2. A member consumer and an **outsider** — `outsider/eve`, a valid fabric identity that is simply not in the audience — both subscribe the same data topic. The member holds 1 key; the outsider holds 0.
3. The producer, a member of its own release-set, unwraps **its own** slot to recover the DEK, seals a message, and publishes the ciphertext on the data topic.
4. The bus delivers the identical bytes to both subscribers. The member opens generation N and prints the plaintext; the outsider is denied — it has no slot for that generation, so the crypto rejects the read.

## What it proves — and why it matters

- **Producer-as-member: no separate key channel.** The producer is in its own audience, so it acquires the DEK by unwrapping its own bundle slot — the same path a consumer uses — rather than being handed the key out of band.
- **The bus broadcasts ciphertext; membership decides readability.** Both subscribers receive the same bytes. Only the one holding a wrapped slot can open them, so the router is never the thing enforcing the read cut.
- **Enrollment is not read authorization.** The outsider is a fully enrolled fabric identity. Being on the fabric lets you receive the ciphertext; it does not give you a key. The two are separate, and this scenario keeps them separate on purpose.

## The honest caveat

The default run uses an in-process bus that models brokerless Zenoh pub/sub — including the `keys/**` retention store, so a late reader can still fetch the current bundle. It is a faithful stand-in, not the router itself. Pass `--fabric` to carry the identical bytes over a real eclipse/zenoh router; that path needs Docker and `pip install eclipse-zenoh` (see `local-fabric/README.md`), and it falls back to the in-process bus if the import is unavailable. Either way the crypto — and therefore the read cut — is identical.

## Run it

The script is the proof companion to this README, not the lesson — read the recipe first, then run:

```
./bin/grant-enc 03
```

To carry the same bytes over a real router instead of the in-process bus:

```
./bin/grant-enc 03 --fabric
```
