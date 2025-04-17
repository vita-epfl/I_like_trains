import sqlite3
import os
import datetime
import logging
import threading
import pytz

STATS_DIR = "stats"
DB_FILENAME = "game_stats.db"  # Single database file
DB_PATH = os.path.join(STATS_DIR, DB_FILENAME)

LOCAL_TZ = pytz.timezone('Europe/Paris')

logger = logging.getLogger(__name__)

local_storage = threading.local()

def get_db_connection():
    """Gets a thread-local database connection."""
    if not hasattr(local_storage, "connection"):
        logger.debug(f"Creating new DB connection for thread {threading.current_thread().name}")
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        local_storage.connection = conn
    return local_storage.connection

def close_db_connection(exception=None):
    """Closes the thread-local database connection."""
    if hasattr(local_storage, "connection"):
        logger.debug(f"Closing DB connection for thread {threading.current_thread().name}")
        local_storage.connection.close()
        del local_storage.connection

def _initialize_database():
    """Initializes the SQLite databases and creates/updates tables."""
    try:        
        os.makedirs(STATS_DIR, exist_ok=True)
        logger.debug(f"Initializing stats directory at {STATS_DIR}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # --- Check table structure --- 
        cursor.execute("PRAGMA table_info(clients)")
        client_columns_info = {column['name']: column for column in cursor.fetchall()}
        client_columns = list(client_columns_info.keys())
        logger.debug(f"Existing columns in 'clients': {client_columns}")

        table_exists = 'clients' in [row['name'] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]

        # --- Ensure all required tables exist --- 
        # Create clients table first if it doesn't exist at all
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                sciper TEXT PRIMARY KEY,
                nickname TEXT,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_connections INTEGER DEFAULT 0,
                total_playtime_seconds INTEGER DEFAULT 0,
                last_connection_time DATETIME,
                last_disconnection_time DATETIME
            )
        """)
        conn.commit() # Commit table creation before altering

        # --- Update existing 'clients' table if it existed before --- 
        if table_exists:
            if 'last_connection_time' not in client_columns:
                logger.info("Adding missing column 'last_connection_time' to 'clients' table.")
                cursor.execute("ALTER TABLE clients ADD COLUMN last_connection_time DATETIME")
            if 'last_disconnection_time' not in client_columns:
                logger.info("Adding missing column 'last_disconnection_time' to 'clients' table.")
                cursor.execute("ALTER TABLE clients ADD COLUMN last_disconnection_time DATETIME")
            
            # Handle total_connections / total_disconnections
            if 'total_connections' not in client_columns:
                if 'total_disconnections' in client_columns:
                    logger.info("Renaming column 'total_disconnections' to 'total_connections' in 'clients' table.")
                    cursor.execute("ALTER TABLE clients RENAME COLUMN total_disconnections TO total_connections")
                else:
                    logger.info("Adding missing column 'total_connections' to 'clients' table.")
                    cursor.execute("ALTER TABLE clients ADD COLUMN total_connections INTEGER DEFAULT 0")
            elif 'total_disconnections' in client_columns:
                # Both exist? Should not happen, but remove total_disconnections if it does
                logger.warning("Both 'total_connections' and 'total_disconnections' columns exist. Removing 'total_disconnections'.")
                try:
                    # SQLite requires a complex workaround for dropping columns before 3.35.0
                    # Create a new table without the column, copy data, drop old, rename new.
                    cursor.execute("PRAGMA foreign_keys=off")
                    conn.commit() # Commit before schema changes
                    cursor.execute("BEGIN TRANSACTION")
                    cursor.execute("""
                        CREATE TABLE clients_new (
                            sciper TEXT PRIMARY KEY,
                            nickname TEXT,
                            wins INTEGER DEFAULT 0,
                            losses INTEGER DEFAULT 0,
                            total_connections INTEGER DEFAULT 0,
                            total_playtime_seconds INTEGER DEFAULT 0,
                            last_connection_time DATETIME,
                            last_disconnection_time DATETIME
                        )
                    """)
                    cols_to_copy = [c for c in client_columns if c != 'total_disconnections']
                    cols_str = ', '.join(cols_to_copy)
                    cursor.execute(f"INSERT INTO clients_new ({cols_str}) SELECT {cols_str} FROM clients")
                    cursor.execute("DROP TABLE clients")
                    cursor.execute("ALTER TABLE clients_new RENAME TO clients")
                    cursor.execute("COMMIT")
                    cursor.execute("PRAGMA foreign_keys=on")
                    logger.info("Successfully removed 'total_disconnections' by recreating 'clients' table.")
                    conn.commit() # Commit after schema changes
                except sqlite3.Error as oe:
                    conn.rollback() # Rollback transaction on error
                    cursor.execute("PRAGMA foreign_keys=on") # Ensure foreign keys are re-enabled
                    logger.error(f"Failed to remove column 'total_disconnections': {oe}")

            # Ensure total_playtime_seconds exists (might have been missed if table was very old)
            if 'total_playtime_seconds' not in client_columns:
                logger.info("Adding missing column 'total_playtime_seconds' to 'clients' table.")
                cursor.execute("ALTER TABLE clients ADD COLUMN total_playtime_seconds INTEGER DEFAULT 0")
            
            # Dropping total_disconnections column if it exists
            if 'total_disconnections' in client_columns:
                 logger.info("Dropping column 'total_disconnections' from 'clients' table.")
                 try:
                     # SQLite requires a complex workaround for dropping columns before 3.35.0
                     # Create a new table without the column, copy data, drop old, rename new.
                     # This is safer than ALTER TABLE DROP COLUMN which might not be supported.
                     cursor.execute("PRAGMA foreign_keys=off")
                     conn.commit() # Commit before schema changes
                     cursor.execute("BEGIN TRANSACTION")
                     cursor.execute("""
                         CREATE TABLE clients_new (
                             sciper TEXT PRIMARY KEY,
                             nickname TEXT,
                             wins INTEGER DEFAULT 0,
                             losses INTEGER DEFAULT 0,
                             total_connections INTEGER DEFAULT 0,
                             total_playtime_seconds INTEGER DEFAULT 0,
                             last_connection_time DATETIME,
                             last_disconnection_time DATETIME
                         )
                     """)
                     cols_to_copy = [c for c in client_columns if c != 'total_disconnections']
                     cols_str = ', '.join(cols_to_copy)
                     cursor.execute(f"INSERT INTO clients_new ({cols_str}) SELECT {cols_str} FROM clients")
                     cursor.execute("DROP TABLE clients")
                     cursor.execute("ALTER TABLE clients_new RENAME TO clients")
                     cursor.execute("COMMIT")
                     cursor.execute("PRAGMA foreign_keys=on")
                     logger.info("Successfully dropped 'total_disconnections' by recreating 'clients' table.")
                     conn.commit() # Commit after schema changes
                 except sqlite3.Error as oe:
                     conn.rollback() # Rollback transaction on error
                     cursor.execute("PRAGMA foreign_keys=on") # Ensure foreign keys are re-enabled
                     logger.error(f"Failed to drop column 'total_disconnections': {oe}")

        # Re-fetch columns after potential changes
        cursor.execute("PRAGMA table_info(clients)")
        client_columns = [column['name'] for column in cursor.fetchall()]
        logger.debug(f"Final columns in 'clients' after update: {client_columns}")

        # Remove client_bot_matches table
        cursor.execute("DROP TABLE IF EXISTS client_bot_matches")

        # Re-add connections_log table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS connections_log (
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            sciper TEXT,
            type TEXT -- 'connect' or 'disconnect'
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_connections_log_timestamp ON connections_log (timestamp)")

        # Keep connections_daily & connections_hourly
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS connections_daily (
                date TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS connections_hourly (
                datetime TEXT PRIMARY KEY, -- YYYY-MM-DD HH:00:00
                count INTEGER DEFAULT 0
            )
        """)

        # Remove old/unused tables if they exist
        # cursor.execute("DROP TABLE IF EXISTS client_bot_matches") # Already done above
        cursor.execute("DROP TABLE IF EXISTS server_info")
        cursor.execute("DROP TABLE IF EXISTS last_match_scores")

        # Re-add bot_vs_human_last_scores table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_vs_human_last_scores (
            human_sciper TEXT NOT NULL,
            bot_nickname TEXT NOT NULL,
            human_score INTEGER,
            bot_score INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (human_sciper, bot_nickname)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bvh_timestamp ON bot_vs_human_last_scores (timestamp)")

        conn.commit()
        logger.info(f"Single database initialized/verified at {DB_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Error initializing database at {DB_PATH}: {e}")
        # Rollback if in transaction during schema change failure
        try:
            if conn.in_transaction:
                 conn.rollback()
                 logger.info("Rolled back transaction due to initialization error.")
        except Exception as rollback_err:
            logger.error(f"Error during rollback attempt: {rollback_err}")
        raise
    # No finally close needed as connection is managed thread-locally


# --- Call initialization on module load ---
_initialize_database()


# --- Functions to record stats ---
def record_connection(sciper: str, nickname: str):
    """Records a client connection, updates client info, and connection counts."""
    now = datetime.datetime.now(LOCAL_TZ)
    today = now.strftime("%Y-%m-%d")
    current_hour_str = now.strftime("%H:00")
    logger.info(f"Recording connection for {nickname} ({sciper}) at {now}")

    # Update Client DB
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logger.debug(f"Executing INSERT OR UPDATE for client {sciper}...")
        cursor.execute(
            """
            INSERT INTO clients (sciper, nickname, last_connection_time, total_connections)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(sciper) DO UPDATE SET
                nickname = excluded.nickname,
                last_connection_time = excluded.last_connection_time,
                total_connections = total_connections + 1
        """,
            (sciper, nickname, now),
        )
        conn.commit()
        logger.debug(f"Client DB changes committed for {sciper}.")
    except sqlite3.Error as e:
        logger.error(
            f"SQLite Error updating client DB during connection for {sciper}: {e}"
        )

    # Update Server DB (Daily/Hourly Connections)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Daily count
        cursor.execute(
            """
            INSERT INTO connections_daily (date, count) VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET count = count + 1
        """,
            (today,),
        )
        # Hourly count
        cursor.execute(
            """
            INSERT INTO connections_hourly (datetime, count) VALUES (?, 1)
            ON CONFLICT(datetime) DO UPDATE SET count = count + 1
        """,
            (current_hour_str,),
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error updating server connection counts in {DB_PATH}: {e}")

    # Record connection in connections_log
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO connections_log (sciper, type, timestamp) VALUES (?, 'connect', ?)
        """,
            (sciper, now),
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error recording connection in connections_log: {e}")


def record_disconnection(
    sciper: str,
    premature: bool
):
    """Records a client disconnection, updates playtime and disconnect count."""
    now = datetime.datetime.now(LOCAL_TZ)
    logger.info(f"Recording disconnection for {sciper} at {now}. Premature: {premature}")

    # Calculate duration based on last connection time
    duration_seconds = 0
    last_conn_time_str = None
    conn = None # Initialize conn to None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT last_connection_time FROM clients WHERE sciper = ?", (sciper,))
        result = cursor.fetchone()
        if result and result["last_connection_time"]:
            last_conn_time_str = result["last_connection_time"]
            logger.debug(f"[Disconnect Debug] Fetched last_connection_time string: '{last_conn_time_str}' for {sciper}")
            last_conn_time = datetime.datetime.fromisoformat(last_conn_time_str).replace(tzinfo=pytz.utc).astimezone(LOCAL_TZ)
            duration_seconds = (now - last_conn_time).total_seconds()
            # Ensure duration is not negative (e.g., clock skew or bad data)
            duration_seconds = max(0, duration_seconds)
            logger.debug(f"[Disconnect Debug] Sciper: {sciper}, LastConnTime: {last_conn_time}, Now: {now}, Calculated Duration: {duration_seconds}s")
        else:
            logger.warning(f"Could not find last_connection_time for {sciper} to calculate duration.")

        # Update Client DB
        update_query = (
            "UPDATE clients SET total_playtime_seconds = total_playtime_seconds + ?,"
            " last_disconnection_time = ?"
        )
        # Use rounded duration_seconds for the update
        # Use 'now' directly for last_disconnection_time
        current_time_for_db = now 
        params = [round(duration_seconds), current_time_for_db]
        logger.debug(f"[Disconnect Debug] Base params for update: playtime_add={params[0]}, last_disconnect_time={params[1]}")

        # We no longer update total_disconnections, as we're using total_connections instead
        # The premature flag is now ignored for column updates

        update_query += " WHERE sciper = ?"
        params.append(sciper)
        logger.debug(f"[Disconnect Debug] Final query: {update_query}")
        logger.debug(f"[Disconnect Debug] Final params: {tuple(params)}")

        cursor.execute(update_query, tuple(params))
        rowcount = cursor.rowcount # Get affected row count
        logger.debug(f"[Disconnect Debug] UPDATE affected {rowcount} row(s) for sciper {sciper}.")

        conn.commit() # Commit the update
        logger.info(f"[Disconnect Commit] Committed playtime/disconnection update for {sciper} at {current_time_for_db}. Rowcount was: {rowcount}.") # Log after commit

    except sqlite3.Error as e:
        logger.error(
            f"Error recording client disconnection for {sciper} in {DB_PATH}: {e}"
        )
        if conn:
            try:
                conn.rollback() # Rollback on error
                logger.info(f"Rolled back disconnection transaction for {sciper}")
            except Exception as rb_err:
                logger.error(f"Error during rollback attempt for {sciper}: {rb_err}")
    except ValueError as ve:
         logger.error(
            f"Error parsing last_connection_time ('{last_conn_time_str}') for {sciper}: {ve}"
        )

    # Record disconnection in connections_log
    try:
        conn = get_db_connection() # Ensure connection
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO connections_log (sciper, type, timestamp) VALUES (?, 'disconnect', ?)
        """,
            (sciper, now),
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error recording disconnection in connections_log: {e}")


def record_game_result(
    sciper: str, win: bool, opponent_name: str, opponent_is_bot: bool
):
    """Records the result of a game for a specific client."""
    try:
        logger.debug(
            f"Recording game result for {sciper} - win: {win}, opponent: {opponent_name}, is_bot: {opponent_is_bot}"
        )
        conn = get_db_connection()
        cursor = conn.cursor()
        column_to_update = "wins" if win else "losses"
        cursor.execute(
            f"""
            UPDATE clients
            SET {column_to_update} = {column_to_update} + 1
            WHERE sciper = ?
        """,
            (sciper,),
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(
            f"Error updating client game result (vs human) for {sciper} in {DB_PATH}: {e}"
        )


# Renamed from record_last_match_score
def record_bot_vs_human_score(human_sciper: str, bot_nickname: str, human_score: int, bot_score: int):
    """Records the scores of the last match between a specific human and bot."""
    p1_id, p2_id = human_sciper, bot_nickname
    p1_score, p2_score = human_score, bot_score

    now = datetime.datetime.now(LOCAL_TZ)
    now_iso = now.isoformat()
    logger.debug(
        f"Recording bot vs human score: {p1_id} ({p1_score}) vs {p2_id} ({p2_score})"
    )

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bot_vs_human_last_scores (human_sciper, bot_nickname, human_score, bot_score, timestamp)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(human_sciper, bot_nickname) DO UPDATE SET
                human_score = excluded.human_score,
                bot_score = excluded.bot_score,
                timestamp = excluded.timestamp
        """,
            (p1_id, p2_id, p1_score, p2_score, now_iso),
        )
        conn.commit()
    except sqlite3.Error as e:
        logger.error(
            f"Error recording bot vs human score between {p1_id} and {p2_id} in {DB_PATH}: {e}"
        )


# --- Function to retrieve and format stats for logging ---
def get_stats_as_string() -> str:
    """Retrieves all stats from the databases and formats them into a string."""
    logger.debug("Retrieving stats...")
    output = ["--- Client Statistics ---"]
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get client stats
        cursor.execute("SELECT * FROM clients ORDER BY sciper")
        clients = cursor.fetchall()
        if not clients:
            output.append("No client data available.")
        else:
            output.append(
                "SCIPER | Nickname         | Wins | Losses | Conn. | Playtime (H:M:S) | Last Connection     | Last Disconnection"
            )
            output.append(
                "-" * 110
            )
            for client in clients:
                playtime_sec = client["total_playtime_seconds"] or 0
                playtime_hms = str(datetime.timedelta(seconds=round(playtime_sec)))
                last_conn = client['last_connection_time'] if client['last_connection_time'] else 'N/A'
                last_disc = client['last_disconnection_time'] if client['last_disconnection_time'] else 'N/A'

                output.append(
                    f"{client['sciper']:<6} | {client['nickname']:<16} | {client['wins']:<4} | {client['losses']:<6} | "
                    f"{client['total_connections']:<5} | {playtime_hms:<16} | {str(last_conn):<19} | {str(last_disc)}"
                )

    except sqlite3.Error as e:
        logger.error(f"Error retrieving client stats: {e}")
        output.append(f"Error retrieving client stats: {e}")
    except KeyError as ke:
        logger.error(f"Error accessing client stats key: {ke}. Current DB schema might be incorrect.")
        output.append(f"Error accessing client stats key: {ke}. Schema issue?")

    # Add Bot vs Human Scores Section
    output.append("\n--- Last Bot vs Human Scores (Last 20) ---")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT human_sciper, bot_nickname, human_score, bot_score, timestamp "
            "FROM bot_vs_human_last_scores ORDER BY timestamp DESC LIMIT 20"
        )
        scores = cursor.fetchall()
        if not scores:
            output.append("No bot vs human scores available.")
        else:
            output.append(
                "Human SCIPER | Bot Nickname     | H Score | B Score | Timestamp"
            )
            output.append("-" * 70)
            for score in scores:
                # Format timestamp to HH:MM
                try:
                    ts_dt = datetime.datetime.fromisoformat(score['timestamp'])
                    formatted_ts = ts_dt.strftime('%H:%M')
                except (ValueError, TypeError):
                    formatted_ts = score['timestamp'] # Fallback if parsing fails

                output.append(
                    f"{score['human_sciper']:<12} | {score['bot_nickname']:<16} | "
                    f"{score['human_score']:<7} | {score['bot_score']:<7} | {formatted_ts:<5}" # Display HH:MM
                )
    except sqlite3.Error as e:
        logger.error(f"Error retrieving bot vs human scores: {e}")
        output.append(f"Error retrieving bot vs human scores: {e}")

    # Keep Daily/Hourly Connection Stats
    output.append("\n--- Connection Statistics ---")
    try:
        conn = get_db_connection() # Ensure we have connection
        cursor = conn.cursor()

        # Get daily connections (last 30 days for brevity)
        output.append("\nConnections per Day (Last 30 Days):")
        cursor.execute(
            "SELECT date, count FROM connections_daily ORDER BY date DESC LIMIT 30"
        )
        daily = cursor.fetchall()
        if daily:
            for row in reversed(daily):
                output.append(f"  {row['date']}: {row['count']}")
        else:
            output.append("  No daily connection data.")

        # Get hourly connections (last 24 hours for brevity)
        output.append("\nConnections per Hour (Last 24 Hours):")
        cursor.execute(
            "SELECT datetime as hour, SUM(count) as total_count "
            "FROM connections_hourly "
            "GROUP BY hour ORDER BY hour ASC" # Group/Order by the hour
        )
        hourly = cursor.fetchall()
        if hourly:
            for row in hourly:
                 # hour is already in the format 'HH:00'
                output.append(f"  {row['hour']}: {row['total_count']}") # Display hour only
        else:
            output.append("  No hourly connection data for the last 24 hours.")

    except sqlite3.Error as e:
        logger.error(f"Error retrieving server stats: {e}")
        output.append(f"Error retrieving server stats: {e}")

    return "\n".join(output)
