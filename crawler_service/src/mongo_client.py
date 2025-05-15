from pymongo import MongoClient

class MongoDBClient:
    def __init__(self, host="localhost", port=27017, username="admin", password="secretpassword", db_name="house_pricing_forecast"):
        self.client = MongoClient(
            host=host,
            port=port,
            username=username,
            password=password,
            authSource="admin",  
            authMechanism="SCRAM-SHA-256"
        )
        self.db = self.client[db_name]
        self.collection = self.db["raw_data"]

    def insert_listings(self, listings):
        if listings:
            self.collection.insert_many(listings)