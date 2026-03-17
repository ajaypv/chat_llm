import os 
import array
import oracledb
from contextlib import contextmanager
from dotenv import load_dotenv
import logging
load_dotenv()

logger = logging.getLogger(__name__)

class RAGDBConnection:
    """Singleton for database connection pool and operations."""
    _instance = None
    _initialized = False
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if RAGDBConnection._initialized:
            return
        RAGDBConnection._initialized = True
        
        self._config_dir = os.getenv("DB_WALLET_PATH")
        self._wallet_location = os.getenv("DB_WALLET_PATH")
        self._wallet_password = os.getenv("DB_WALLET_PASSWORD")

        # Support both env var spellings.
        self._user = os.getenv("DB_USER") or os.getenv("DB_USERNAME")
        self._password = os.getenv("DB_PASSWORD")
        self._dsn = os.getenv("DB_DSN")

        self.table_prefix = os.getenv("DB_TABLE_PREFIX") or "edge_demo"
    
    def _get_pool(self) -> oracledb.ConnectionPool:
        """Get or create the connection pool (lazy initialization)."""
        if RAGDBConnection._pool is None:
            logger.info("Creating Oracle connection pool")
            RAGDBConnection._pool = oracledb.create_pool(
                user=self._user,
                password=self._password,
                dsn=self._dsn,
                config_dir=self._config_dir,
                wallet_location=self._wallet_location,
                wallet_password=self._wallet_password,
                min=1,
                max=5,
                increment=1,
                ping_interval=30,
            )
        return RAGDBConnection._pool

    def reset_pool(self) -> None:
        pool = RAGDBConnection._pool
        RAGDBConnection._pool = None
        if pool is None:
            return
        try:
            logger.warning("Closing stale Oracle connection pool")
            pool.close(force=True)
        except Exception as exc:
            logger.warning("Failed closing Oracle pool cleanly: %s", exc)

    @staticmethod
    def is_connection_error(exc: Exception) -> bool:
        text = str(exc or "")
        return any(code in text for code in ("DPY-4011", "DPY-1001", "DPI-1080", "ORA-03113", "ORA-03114"))
    
    @contextmanager
    def get_connection(self):
        """Context manager for acquiring a connection from the pool.
        
        Usage:
            with db.get_connection() as conn:
                cols, rows = db.execute_query(conn, sql)
        """
        conn = None
        pool = None
        for attempt in range(2):
            pool = self._get_pool()
            try:
                conn = pool.acquire()
                break
            except Exception as exc:
                if attempt == 0 and self.is_connection_error(exc):
                    logger.warning("Oracle pool acquire failed due to stale connection, resetting pool: %s", exc)
                    self.reset_pool()
                    continue
                raise

        if conn is None or pool is None:
            raise RuntimeError("failed to acquire Oracle connection")

        try:
            yield conn
        except Exception as exc:
            if self.is_connection_error(exc):
                logger.warning("Oracle connection error during DB operation, dropping pool: %s", exc)
                try:
                    conn.close()
                except Exception:
                    pass
                self.reset_pool()
                conn = None
            raise
        finally:
            if conn is not None:
                try:
                    pool.release(conn)
                except Exception:
                    pass

    def connect_db(self) -> oracledb.Connection:
        try:
            return oracledb.connect(
                user=self._user,
                password=self._password,
                dsn=self._dsn,
                config_dir=self._config_dir,
                wallet_location=self._wallet_location,
                wallet_password=self._wallet_password,
            )
        except oracledb.Error as exc:
            print(f"ERROR: DB connection failed: {exc}")
            raise exc
    
    def disconnect(self, connection: oracledb.Connection):
        connection.close()
    
    def get_cursor(self):
        self.db_connection = self.connect_db()
        self.cursor = self.db_connection.cursor()

    def execute_query(self, conn: oracledb.Connection, sql: str):
        """Execute SQL query and return column names and rows."""
        with conn.cursor() as cur:
            cur.execute(sql)
            return [d[0] for d in cur.description], cur.fetchall()

    def create_table(self, conn: oracledb.Connection):
        """Drop and create embedding table."""
        print("Creating table for embeddings...")

        # Use the prefix to avoid usage of the same table per user
        sql_statements = [
            f"DROP TABLE {self.table_prefix}_embedding PURGE",
            f"""
            CREATE TABLE {self.table_prefix}_embedding (
                id NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                text VARCHAR2(4000),
                embedding_vector VECTOR,
                chapter VARCHAR2(100),
                section INTEGER,
                source VARCHAR2(100)
            )
            """
        ]

        with conn.cursor() as cur:
            for stmt in sql_statements:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    print(f"Skipping error: {e}")

    def insert_embedding(self, conn: oracledb.Connection, embeddings, texts, splits):
        for i, emb in enumerate(embeddings):
            chunk_text = texts[i][:3900]  # ensure within VARCHAR2(4000) limit according to table constraint
            metadata_source = str(splits[i].metadata.get('source', 'pdf-doc'))
            chapter = splits[i].metadata.get('source', 'unknown')[:100] if splits[i].metadata.get('source') else 'unknown'
            section = splits[i].metadata.get('page', 0)

            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {self.table_prefix}_embedding (text, embedding_vector, chapter, section, source) VALUES (:1, :2, :3, :4, :5)",
                    [chunk_text, array.array("f", emb), chapter, int(section) if section else 0, metadata_source],
                )

        conn.commit()


def ensure_knowledge_tables(conn: oracledb.Connection, table_prefix: str) -> None:
    with conn.cursor() as cur:
        # File registry
        try:
            cur.execute(
                f"""
                CREATE TABLE {table_prefix}_knowledge_file (
                  id NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  category VARCHAR2(64) NOT NULL,
                  filename VARCHAR2(255) NOT NULL,
                  storage_path VARCHAR2(1024) NOT NULL,
                  bytes NUMBER,
                  created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
                )
                """
            )
        except Exception:
            pass

        try:
            cur.execute(f"CREATE INDEX {table_prefix}_kf_cat_idx ON {table_prefix}_knowledge_file(category)")
        except Exception:
            pass

        # Job queue (batch)
        try:
            cur.execute(
                f"""
                CREATE TABLE {table_prefix}_knowledge_job (
                  id NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                  status VARCHAR2(16) NOT NULL,
                  progress_pct NUMBER DEFAULT 0 NOT NULL,
                  message VARCHAR2(1000),
                  created_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
                  updated_at TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
                  started_at TIMESTAMP,
                  finished_at TIMESTAMP
                )
                """
            )
        except Exception:
            pass

        try:
            cur.execute(f"CREATE INDEX {table_prefix}_kj_status_idx ON {table_prefix}_knowledge_job(status)")
        except Exception:
            pass

        # Map files to jobs
        try:
            cur.execute(
                f"""
                CREATE TABLE {table_prefix}_knowledge_job_file (
                  job_id NUMBER NOT NULL,
                  file_id NUMBER NOT NULL,
                  CONSTRAINT {table_prefix}_kjf_job_fk FOREIGN KEY (job_id) REFERENCES {table_prefix}_knowledge_job(id),
                  CONSTRAINT {table_prefix}_kjf_file_fk FOREIGN KEY (file_id) REFERENCES {table_prefix}_knowledge_file(id)
                )
                """
            )
        except Exception:
            pass

        try:
            cur.execute(f"CREATE INDEX {table_prefix}_kjf_job_idx ON {table_prefix}_knowledge_job_file(job_id)")
        except Exception:
            pass

    conn.commit()


def create_knowledge_file(conn: oracledb.Connection, table_prefix: str, category: str, filename: str, storage_path: str, size_bytes: int | None) -> int:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"create_knowledge_file: category={category}, filename={filename}, storage_path={storage_path}")
    with conn.cursor() as cur:
        out_id = cur.var(oracledb.NUMBER)
        cur.execute(
            f"""
            INSERT INTO {table_prefix}_knowledge_file (category, filename, storage_path, bytes)
            VALUES (:1, :2, :3, :4)
            RETURNING id INTO :5
            """,
            [category, filename, storage_path, size_bytes, out_id],
        )
        file_id = int(out_id.getvalue()[0])
        logger.info(f"create_knowledge_file: created file_id={file_id}")
    conn.commit()
    logger.info(f"create_knowledge_file: committed")
    return file_id


def create_knowledge_job(conn: oracledb.Connection, table_prefix: str) -> int:
    with conn.cursor() as cur:
        out_id = cur.var(oracledb.NUMBER)
        cur.execute(
            f"""
            INSERT INTO {table_prefix}_knowledge_job (status, progress_pct, message, updated_at)
            VALUES ('queued', 0, NULL, SYSTIMESTAMP)
            RETURNING id INTO :1
            """,
            [out_id],
        )
        job_id = int(out_id.getvalue()[0])
    conn.commit()
    return job_id


def add_file_to_job(conn: oracledb.Connection, table_prefix: str, job_id: int, file_id: int) -> None:
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"add_file_to_job: job_id={job_id}, file_id={file_id}")
    with conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO {table_prefix}_knowledge_job_file (job_id, file_id) VALUES (:1, :2)",
            [job_id, file_id],
        )
    conn.commit()
    logger.info(f"add_file_to_job: committed link between job #{job_id} and file #{file_id}")


def update_knowledge_job(conn: oracledb.Connection, table_prefix: str, job_id: int, status: str | None = None, progress_pct: int | None = None, message: str | None = None) -> None:
    sets: list[str] = ["updated_at = SYSTIMESTAMP"]
    params: list[object] = []
    if status is not None:
        sets.append("status = :status")
        params.append(status)
    if progress_pct is not None:
        sets.append("progress_pct = :progress_pct")
        params.append(int(progress_pct))
    if message is not None:
        sets.append("message = :message")
        params.append(message[:1000])

    if not params:
        return

    # Build named binds in a stable order
    bind = {"job_id": job_id}
    if status is not None:
        bind["status"] = status
    if progress_pct is not None:
        bind["progress_pct"] = int(progress_pct)
    if message is not None:
        bind["message"] = message[:1000]

    sql = f"UPDATE {table_prefix}_knowledge_job SET {', '.join(sets)} WHERE id = :job_id"
    with conn.cursor() as cur:
        cur.execute(sql, bind)
    conn.commit()


def get_knowledge_job(conn: oracledb.Connection, table_prefix: str, job_id: int) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT j.id, j.status, j.progress_pct, j.message
            FROM {table_prefix}_knowledge_job j
            WHERE j.id = :1
            """,
            [job_id],
        )
        row = cur.fetchone()
        if not row:
            return None
        job = {
            "id": int(row[0]),
            "status": str(row[1]),
            "progress_pct": int(row[2]),
            "message": row[3] if row[3] is None else str(row[3]),
        }

        cur.execute(
            f"""
            SELECT f.id, f.category, f.filename, f.storage_path, f.bytes
            FROM {table_prefix}_knowledge_job_file jf
            JOIN {table_prefix}_knowledge_file f ON f.id = jf.file_id
            WHERE jf.job_id = :1
            ORDER BY f.created_at
            """,
            [job_id],
        )
        files = []
        for r in cur.fetchall() or []:
            files.append(
                {
                    "id": int(r[0]),
                    "category": str(r[1]),
                    "filename": str(r[2]),
                    "storage_path": str(r[3]),
                    "bytes": None if r[4] is None else int(r[4]),
                }
            )
        job["files"] = files
        return job


def claim_next_knowledge_job(conn: oracledb.Connection, table_prefix: str) -> dict | None:
    """Atomically claim a queued job and mark it as running."""
    with conn.cursor() as cur:
        # First, find the next queued job (without locking)
        cur.execute(
            f"""
            SELECT id
            FROM {table_prefix}_knowledge_job
            WHERE status = 'queued'
            ORDER BY created_at
            FETCH FIRST 1 ROWS ONLY
            """
        )
        row = cur.fetchone()
        if not row:
            return None
        job_id = int(row[0])
        
        # Try to lock and update it atomically
        cur.execute(
            f"""
            SELECT id
            FROM {table_prefix}_knowledge_job
            WHERE id = :1 AND status = 'queued'
            FOR UPDATE SKIP LOCKED
            """,
            [job_id]
        )
        locked_row = cur.fetchone()
        if not locked_row:
            # Someone else claimed it, recurse to try next
            conn.rollback()
            return claim_next_knowledge_job(conn, table_prefix)
        
        cur.execute(
            f"""
            UPDATE {table_prefix}_knowledge_job
            SET status = 'running', progress_pct = 0, message = 'started',
                updated_at = SYSTIMESTAMP, started_at = SYSTIMESTAMP
            WHERE id = :1
            """,
            [job_id],
        )
    conn.commit()
    return get_knowledge_job(conn, table_prefix, job_id)


def finish_knowledge_job(conn: oracledb.Connection, table_prefix: str, job_id: int, ok: bool, message: str | None = None) -> None:
    status = 'completed' if ok else 'failed'
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {table_prefix}_knowledge_job
            SET status = :1,
                progress_pct = CASE WHEN :2 = 'completed' THEN 100 ELSE progress_pct END,
                message = :3,
                updated_at = SYSTIMESTAMP,
                finished_at = SYSTIMESTAMP
            WHERE id = :4
            """,
            [status, status, (message or '')[:1000], job_id],
        )
    conn.commit()


def create_knowledge_delete_job(conn: oracledb.Connection, table_prefix: str, category: str) -> int:
    with conn.cursor() as cur:
        out_id = cur.var(oracledb.NUMBER)
        cur.execute(
            f"""
            INSERT INTO {table_prefix}_knowledge_job (status, progress_pct, message, updated_at)
            VALUES ('queued', 0, :message, SYSTIMESTAMP)
            RETURNING id INTO :job_id
            """,
            {"message": f"delete:{category}"[:1000], "job_id": out_id},
        )
        job_id = int(out_id.getvalue()[0])
    conn.commit()
    return job_id


def get_knowledge_delete_job(conn: oracledb.Connection, table_prefix: str, job_id: int) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, status, progress_pct, message, created_at, updated_at, started_at, finished_at
            FROM {table_prefix}_knowledge_job
            WHERE id = :job_id
            """,
            {"job_id": job_id},
        )
        row = cur.fetchone()
        if not row:
            return None
        message = row[3] if row[3] is None else str(row[3])
        category = ""
        if message and message.startswith("delete:"):
            category = message.split(":", 1)[1]
        return {
            "id": int(row[0]),
            "status": str(row[1]),
            "progress_pct": int(row[2]),
            "message": message,
            "category": category,
        }
