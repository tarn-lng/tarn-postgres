# tarn-postgres

A native, zero-dependency PostgreSQL client driver written 100% in [Tarn](https://github.com/tarn-lng/tarn).

Implements the PostgreSQL Frontend/Backend Protocol 3.0 directly over native TCP sockets (`stdlib/net`). Does not require `libpq`, C compilers, or native library linking.

## Features

- **100% Pure Tarn**: Implemented purely in safe Tarn systems code over `net.TcpStream`.
- **Zero C Dependencies**: No `libpq-dev` or `--link pq` needed.
- **Protocol 3.0 Wire Implementation**: Native binary message encoding and decoding (StartupMessage, Authentication, ParameterStatus, RowDescription, DataRow, CommandComplete, ReadyForQuery, Terminate).
- **Type-Safe API**:
  - `Client.connect(Config)`
  - `Client.query(&string)` -> `QueryResult` with rows, column names, and command tags.
  - `Client.execute(&string)` -> command status tags (`CREATE TABLE`, `INSERT`, `UPDATE`, `DELETE`).
  - `Client.close()` -> graceful session shutdown.

## Quick Start

### 1. Run PostgreSQL in Docker

```bash
docker run -d --name tarn-postgres -p 5432:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=testdb \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  postgres:17-alpine
```

### 2. Code Example

```tarn
import "lib"

fn main() {
    cfg := lib.Config.default() // 127.0.0.1:5432, postgres, testdb
    var client = try lib.Client.connect(cfg)

    // Execute DDL
    try client.execute(&"CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT);")

    // Insert data
    try client.execute(&"INSERT INTO users (name) VALUES ('Ada Lovelace'), ('Alan Turing');")

    // Query rows
    res := try client.query(&"SELECT id, name FROM users ORDER BY id;")
    for r in res.rows.as_slice() {
        print(r.get_or(0, "?") + " - " + r.get_or(1, "?"))
    }

    try client.close()
}
```

### 3. Run the Demo

```bash
tarn run main.tarn
```

Output:
```text
==================================================
  Tarn PostgreSQL Native Driver v0.1.0
  Pure Tarn · Zero C Dependencies · Docker Test
==================================================
Connecting to PostgreSQL at 127.0.0.1:5432 (testdb)...
✓ Connection established! Protocol 3.0 Handshake OK.

[1] Creating 'products' table...
    DROP TABLE 
    CREATE TABLE 

[2] Inserting inventory rows...
    INSERT 0 5 

[3] Querying filtered products (price > 40.00)...
    Rows returned: 3
    ------------------------------------------------------
    #2 | 27-inch 4K Monitor (Hardware) - $349.50
    #4 | Noise Cancelling Headphones (Audio) - $199.00
    #1 | Mechanical Keyboard (Hardware) - $129.99
    ------------------------------------------------------

[4] Running aggregation query...
    Summary: 5 items | Min: $19.99 | Max: $349.50

[5] Closing database session...
✓ Session terminated cleanly with Terminate ('X') packet.
```

## License

MIT / Apache 2.0

## TLS, SCRAM-SHA-256 and Transaction Support (v0.5.0)

The driver supports verified PostgreSQL SSLRequest/TLS through
`net.TlsStream.connect_postgres`, SCRAM-SHA-256, explicit transactions and
`Client.transaction(fn(&mut Client) Result<void, Error>)`. No `libpq` is used.
TLS uses Tarn's system `libcurl.so.4` backend (Tarn 0.3.0+, including the
official `ghcr.io/tarn-lng/tarn:0.3.0` container image). The introductory
zero-native-dependency description above applies to plaintext TCP.

For Neon, configure `sslmode=require` or `sslmode=verify-full`. Both verify the
certificate and hostname; an empty CA file uses system trust. Never use
`sslmode=disable` for Neon. `Config.with_ca_file(path)` supports a development
CA; `Config.with_connect_timeout(milliseconds)` bounds TLS setup. Legacy
`prefer` falls back only when the server explicitly refuses SSL before any
startup or credentials; an offered TLS connection must verify and uses a
credential-free probe plus a second connection. Required TLS uses one connection.

URL credentials are percent-decoded, IPv6 authorities must be bracketed, and
unknown/duplicate security options and invalid ports are rejected. SCRAM uses
OS randomness, bounded iterations, RFC 7677 client proofs and mandatory server
signature verification. ASCII passwords are supported; Unicode SASLprep,
SCRAM-SHA-256-PLUS / `channel_binding=require`, MD5 authentication and per-query
I/O deadlines remain unsupported and are not silently claimed. The setup timeout
does not cover authentication messages or later SQL operations.

Simple and extended query errors drain through ReadyForQuery. Protocol/I/O
failures poison the client; the pool only retains synchronized idle connections.
Transactions must use one acquired `Client`; do not issue BEGIN and COMMIT using
separate `Pool.query` calls. A failed transaction cannot report a successful
COMMIT. The transaction callback rolls back on errors, and the pool discards
connections returned with an unfinished transaction.

Run the local regression suite from this workspace:

```sh
cargo build --manifest-path ../../tarn/Cargo.toml -p tarn
sh tests/test.sh
```

The suite uses ephemeral loopback-only PostgreSQL 17 in Docker, a generated
self-signed test certificate and disposable credentials. It does not access or
modify an existing database. Set `POSTGRES_TEST_IMAGE` to another locally
available PostgreSQL 17 image if needed. The protocol fixtures also test invalid
SCRAM server proofs, missing authentication, malformed lengths and truncated rows.
