# tars-core

Shared runtime plumbing, MQTT adapters, and Pydantic contracts for the TARS stack.

This package is the canonical home for the `tars` namespace. It can be installed in
editable mode for local development:

```bash
pip install -e packages/tars-core
```

When building Docker images we will produce a wheel from this package and install it
into each service container.
