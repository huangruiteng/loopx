FROM zli12321/lhtb-nbody-accel-iterative:20260615

COPY . /tests/

# Runtime verification uses the prebuilt numpy and does not need network
# access. The hardening tests are run by the publisher build on the canonical
# image; here we only ensure the shipped verifier entrypoints are executable.
RUN chmod +x /tests/test.sh /tests/submission_runner.py

CMD ["/bin/bash"]
