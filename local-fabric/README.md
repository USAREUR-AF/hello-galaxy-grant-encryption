# local-fabric — carry the same bytes over a real router

Everything in this repo runs with no infrastructure. This directory is the
**optional proof** that the crypto's bytes survive a real Zenoh transport: it
starts one throwaway `eclipse/zenoh:1.9.0` router on `tcp/127.0.0.1:7447` and lets
scenario 03 publish the identical envelope + bundle over it.

## Run it

```bash
docker compose -f local-fabric/docker-compose.yml up -d   # start the router
pip install eclipse-zenoh                                 # the Python client (1.x)
./bin/grant-enc 03 --fabric                               # run scenario 03 over the wire
docker compose -f local-fabric/docker-compose.yml down    # stop + remove it
```

You should see the same result as the default run — a member opens the stream, an
outsider receives the identical bytes and is denied — except the bytes now made a
real round-trip through the router. If `eclipse-zenoh` or docker is missing,
scenario 03 says so and falls back to the in-process bus rather than pretending.

## What this is (and isn't)

- **Is:** a genuine Zenoh 1.9 router moving the real ciphertext + key bundle, with a
  memory storage on `keys/**` so a late reader's `get()` returns the retained
  bundle (mirroring the production key-retention store).
- **Isn't:** the production fabric. This router is plaintext and open, on loopback.
  The real fabric runs mTLS with a per-identity ACL. That difference doesn't affect
  what scenario 03 proves, because **the read cut here is the crypto, not the
  router** — an outsider on this open router still cannot open the stream. See
  [`../docs/honesty-matrix.md`](../docs/honesty-matrix.md).

`zenohd.json5` is the router config; `../lib/zenoh_bus.py` is the client that gives
the real router the same method shape as the in-process bus.
