FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV ELAN_HOME=/usr/local/elan
ENV PATH="${ELAN_HOME}/bin:${PATH}"

RUN apt-get update && apt-get install -y \
    curl \
    git \
    python3 \
    python3-pip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y --default-toolchain none

WORKDIR /app

RUN git clone https://github.com/leanprover-community/mathlib4.git /tmp/mathlib4 \
    && cd /tmp/mathlib4 \
    && git checkout 29dcec074de168ac2bf835a77ef68bbe069194c5

RUN cd /tmp/mathlib4 \
    && elan override set $(cat lean-toolchain) \
    && elan default $(cat lean-toolchain) \
    && lake exe cache get \
    && lake build

ENV LEAN_PATH="/tmp/mathlib4/.lake/build/lib:/tmp/mathlib4/.lake/packages/Qq/.lake/build/lib:/tmp/mathlib4/.lake/packages/aesop/.lake/build/lib:/tmp/mathlib4/.lake/packages/Cli/.lake/build/lib:/tmp/mathlib4/.lake/packages/importGraph/.lake/build/lib:/tmp/mathlib4/.lake/packages/LeanSearchClient/.lake/build/lib:/tmp/mathlib4/.lake/packages/batteries/.lake/build/lib:/tmp/mathlib4/.lake/packages/proofwidgets/.lake/build/lib"

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["python3", "app.py"]
