#(©)CodeXBotz

from database.multi_mongo import mongo_manager


async def _get_users_collection():
    db = await mongo_manager.ensure_database()
    return db["users"]


async def present_user(user_id: int):
    user_data = await _get_users_collection()
    return bool(await user_data.find_one({"_id": user_id}))


async def add_user(user_id: int):
    user_data = await _get_users_collection()
    await user_data.update_one({"_id": user_id}, {"$setOnInsert": {"_id": user_id}}, upsert=True)


async def full_userbase():
    user_data = await _get_users_collection()
    user_ids = []
    async for doc in user_data.find({}, {"_id": 1}):
        user_ids.append(doc["_id"])
    return user_ids


async def del_user(user_id: int):
    user_data = await _get_users_collection()
    await user_data.delete_one({"_id": user_id})
