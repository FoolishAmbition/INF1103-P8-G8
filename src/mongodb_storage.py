
"""MongoDB persistence strategy for EventWise."""

import os

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from src.exceptions import DatabaseError
from src.storage import PersistenceStrategy


class MongoStorage(PersistenceStrategy):
    """Stores and retrieves EventWise data using MongoDB."""

    def __init__(
        self,
        uri: str | None = None,
        database_name: str = "eventwise",
        collection_name: str = "eventwise_data",
    ):
        # Get the MongoDB connection address.
        # Use the environment variable if one is provided.
        # Otherwise, connect to a local MongoDB server.
        self._uri = uri or os.getenv(
            "MONGODB_URI", "mongodb://localhost:27017/"
        )

        try:
            # Create a connection to MongoDB.
            self._client = MongoClient(
                self._uri,
                serverSelectionTimeoutMS=5000,
            )

            # Check whether MongoDB is reachable.
            self._client.admin.command("ping")

            # Select the EventWise database.
            self._database = self._client[database_name]

            # Select the collection used to store profiles and events.
            self._collection = self._database[collection_name]

        except PyMongoError as exc:
            raise DatabaseError(
                f"Could not connect to MongoDB: {exc}"
            ) from exc

    def save(self, key: str, data) -> None:
        """Save or replace a profile or event record."""

        try:
            # Store each type of data using its key as the document ID.
            # If the document already exists, replace its data.
            # If it does not exist, create a new document.
            self._collection.replace_one(
                {"_id": key},
                {"_id": key, "data": data},
                upsert=True,
            )

        except PyMongoError as exc:
            raise DatabaseError(
                f"Could not save {key} to MongoDB: {exc}"
            ) from exc

    def load(self, key: str):
        """Load a profile or event record from MongoDB."""

        try:
            # Find the document with the matching ID.
            document = self._collection.find_one({"_id": key})

            # Return None if the requested data does not exist.
            if document is None:
                return None

            # Return the actual stored data.
            return document["data"]

        except PyMongoError as exc:
            raise DatabaseError(
                f"Could not load {key} from MongoDB: {exc}"
            ) from exc

        except KeyError as exc:
            raise DatabaseError(
                f"Stored document {key} has an invalid structure."
            ) from exc

    def exists(self, key: str) -> bool:
        """Check whether a profile or event record exists."""

        try:
            # Check for a document with the matching ID.
            return self._collection.find_one(
                {"_id": key},
                {"_id": 1},
            ) is not None

        except PyMongoError as exc:
            raise DatabaseError(
                f"Could not check {key} in MongoDB: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the MongoDB connection."""

        self._client.close()
