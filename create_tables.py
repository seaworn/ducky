import asyncio

from db.database import Database

db = Database()


async def main():
    await db.create_tables()


if __name__ == "__main__":
    asyncio.run(main())
