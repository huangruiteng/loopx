FROM zli12321/lhtb-langchain-version-migration:20260615

COPY . /tests/

# The task image already carries the offline wheelhouse. Install the verifier
# runtime here without contacting a registry, and keep the baked test suite.
RUN python -m pip install --no-cache-dir --no-index \
      --find-links /opt/wheelhouse \
      "langchain==1.3.4" \
      "pyyaml==6.0.2" \
      "pytest==8.4.1" \
      "setuptools>=68" \
      "wheel" \
    && chmod +x /tests/test.sh

CMD ["/bin/bash"]
