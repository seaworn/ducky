import asyncio

from db.database import Database

db = Database()


async def main():
    await db.drop_tables()


if __name__ == "__main__":
    asyncio.run(main())
