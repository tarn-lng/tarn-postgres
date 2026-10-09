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
