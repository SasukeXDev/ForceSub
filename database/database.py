#(©)CodeXBotz

from database.multi_mongo import mongo_manager


def _get_users_collection():
    db = mongo_manager.get_database()
    if db is None:
        return None
    return db["users"]


async def present_user(user_id: int):
    user_data = _get_users_collection()
    if user_data is None:
        return False
    return bool(user_data.find_one({"_id": user_id}))


async def add_user(user_id: int):
    user_data = _get_users_collection()
    if user_data is None:
        return
    user_data.update_one({"_id": user_id}, {"$setOnInsert": {"_id": user_id}}, upsert=True)


async def full_userbase():
    user_data = _get_users_collection()
    if user_data is None:
        return []
    return [doc["_id"] for doc in user_data.find({}, {"_id": 1})]


async def del_user(user_id: int):
    user_data = _get_users_collection()
    if user_data is None:
        return
    user_data.delete_one({"_id": user_id})
