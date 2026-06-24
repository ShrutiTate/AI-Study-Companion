import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=dotenv_path)

MONGO_URL = os.getenv("MONGO_URL")

print("[DB] Loading configuration...")
print(f"[DB] MONGO_URL loaded: {bool(MONGO_URL)}")

db = None
client = None
status = "offline"
users_collection = None
sessions_collection = None
chat_collection = None
friend_requests_collection = None
friends_list_collection = None

try:
    if not MONGO_URL:
        raise ValueError("MONGO_URL not found in .env")
    
    print("[DB] Connecting to MongoDB Atlas...")
    # Increase timeout to 30s for slow/distant connections, disable server monitoring warnings
    client = MongoClient(
        MONGO_URL,
        serverSelectionTimeoutMS=30000,
        socketTimeoutMS=30000,
        connectTimeoutMS=30000,
        retryWrites=True,
        directConnection=False
    )
    
    # Force connection check with server_info
    client.server_info()
    
    # Get database
    db = client["echo_connect"]
    
    # Get collections
    users_collection = db["users"]
    sessions_collection = db["sessions"]
    chat_collection = db["chat"]
    friend_requests_collection = db["friend_requests"]
    friends_list_collection = db["friends_list"]
    
    # Create indexes
    try:
        users_collection.create_index("user_id", unique=True)
        sessions_collection.create_index("session_id", unique=True)
        chat_collection.create_index("timestamp")
        
        # Friend Chat Indexes (Completely isolated)
        friend_messages = db["friend_messages"]
        friend_messages.create_index([("sender_id", 1), ("receiver_id", 1), ("timestamp", -1)])
        friend_messages.create_index([("receiver_id", 1), ("read_status", 1)])
        
        # Friend System Indexes
        friend_requests_collection.create_index([("sender_id", 1), ("receiver_id", 1)])
        friend_requests_collection.create_index([("receiver_id", 1), ("status", 1)])
        friends_list_collection.create_index([("user_id", 1)])
        
        print("[DB] SUCCESS: Database indexes created (including Friend Chat)")
    except Exception as e:
        print(f"[DB] WARNING: Could not create indexes: {e}")
    
    status = "connected"
    print("[DB] SUCCESS: Connected to MongoDB Atlas!")
    
except Exception as e:
    print(f"[DB] ERROR: Failed to connect to MongoDB - {str(e)[:100]}")
    print("[DB] WARNING: Running in offline mode - data will not persist")
    print("[DB] TROUBLESHOOTING TIPS:")
    print("[DB]  1. Check MongoDB Atlas dashboard - cluster might be paused")
    print("[DB]  2. Verify your IP is whitelisted in Network Access")
    print("[DB]  3. Check MONGO_URL connection string in .env")
    print("[DB]  4. Ensure MongoDB cluster is running (not M0 free tier paused)")
    status = "offline"
    client = None
    
    # Create robust mock system for offline mode to prevent route crashes
    class MockCursor:
        def __init__(self, data=None):
            self.data = data if data is not None else []
            
        def sort(self, *args, **kwargs):
            return self

        def skip(self, *args, **kwargs):
            return self
            
        def limit(self, *args, **kwargs):
            return self
            
        def __iter__(self):
            return iter(self.data)
            
        def __getitem__(self, index):
            return self.data[index]
            
        def __len__(self):
            return len(self.data)

    class MockCollection:
        def insert_one(self, doc):
            class Result:
                inserted_id = "mock_id"
            return Result()
            
        def update_one(self, filter_dict, update_dict, *args, **kwargs):
            class Result:
                modified_count = 1
            return Result()
            
        def update_many(self, filter_dict, update_dict, *args, **kwargs):
            class Result:
                modified_count = 0
            return Result()
            
        def delete_one(self, filter_dict, *args, **kwargs):
            class Result:
                deleted_count = 1
            return Result()
            
        def find(self, filter_dict=None, *args, **kwargs):
            return MockCursor([])
            
        def find_one(self, filter_dict=None, *args, **kwargs):
            return None
            
        def create_index(self, *args, **kwargs):
            pass

        def count_documents(self, filter_dict=None, *args, **kwargs):
            return 0

    class MockDatabase:
        def __init__(self):
            self.collections = {
                "users": MockCollection(),
                "sessions": MockCollection(),
                "chat": MockCollection(),
                "friend_requests": MockCollection(),
                "friends_list": MockCollection()
            }
            
        def __getitem__(self, name):
            if name not in self.collections:
                self.collections[name] = MockCollection()
            return self.collections[name]
            
    db = MockDatabase()
    users_collection = db["users"]
    sessions_collection = db["sessions"]
    chat_collection = db["chat"]
    friend_requests_collection = db["friend_requests"]
    friends_list_collection = db["friends_list"]


def get_db():
    """Get the database instance"""
    return db



def get_status():
    """Get database connection status"""
    return status


def is_connected():
    """Check if database is connected"""
    return status == "connected"
