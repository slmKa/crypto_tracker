"""
Configuration des connexions aux bases de données
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
import logging
import sys
import os

# Ajouter le path parent pour importer config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config.settings import settings

logger = logging.getLogger(__name__)

def get_timescale_connection():
    """
    Obtenir une connexion TimescaleDB
    
    Returns:
        Connection object ou None si erreur
    """
    try:
        conn = psycopg2.connect(
            host=settings.TIMESCALE_HOST,
            port=settings.TIMESCALE_PORT,
            database=settings.TIMESCALE_DB,
            user=settings.TIMESCALE_USER,
            password=settings.TIMESCALE_PASSWORD,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"Erreur connexion TimescaleDB: {e}")
        return None

def get_redis_connection():
    """
    Obtenir une connexion Redis
    
    Returns:
        Redis client ou None si erreur
    """
    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=5
        )
        r.ping()  # Test de connexion
        return r
    except Exception as e:
        logger.error(f"Erreur connexion Redis: {e}")
        return None

def test_connections():
    """
    Tester toutes les connexions
    
    Returns:
        dict: Statut de chaque connexion
    """
    status = {
        'timescale': False,
        'redis': False
    }
    
    # Test TimescaleDB
    conn = get_timescale_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('SELECT 1')
            cur.close()
            conn.close()
            status['timescale'] = True
        except:
            pass
    
    # Test Redis
    r = get_redis_connection()
    if r:
        try:
            r.ping()
            status['redis'] = True
        except:
            pass
    
    return status