import logging
import os
from google.cloud.sql.connector import Connector, IPTypes
import sqlalchemy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_connection():
  """Tests Cloud SQL connection directly to the 'prism' database."""
  # Load parameters from environment or use defaults for prod
  instance_connection_name = os.getenv(
      "INSTANCE_CONNECTION_NAME"
  )
  db_user = os.getenv("DB_USER", "postgres")
  db_pass = os.getenv("DB_PASS")
  db_name = "prism"

  if not db_pass:
    logger.error("DB_PASS environment variable is not set.")
    print("\nError: DB_PASS is required.")
    print("Please run: export DB_PASS='your-password'")
    return

  logger.info("Initializing Cloud SQL Connector...")
  # Initialize Connector
  connector = Connector()

  def getconn():
    conn = connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_user,
        password=db_pass,
        db=db_name,
        ip_type=IPTypes.PUBLIC,
    )
    return conn

  logger.info(
      "Connecting to %s (database: %s)...", instance_connection_name, db_name
  )
  try:
    # Create connection pool
    pool = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )

    # Test the connection
    with pool.connect() as db_conn:
      result = db_conn.execute(sqlalchemy.text("SELECT NOW()")).fetchone()
      logger.info("Successfully connected to '%s' database!", db_name)
      logger.info("Current Database Time: %s", result[0])

  except Exception as e:
    logger.error("Failed to connect to '%s': %s", db_name, e)
  finally:
    connector.close()


if __name__ == "__main__":
  test_connection()
