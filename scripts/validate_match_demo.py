import asyncio
import sys

sys.path.append(".")

from app.db.session import AsyncSessionLocal, redis_client
from app.services.validation_service import ValidationService


async def main():
    async with AsyncSessionLocal() as session:
        service = ValidationService(session, redis_client)

        print("--- Validating Match 1 (Should remain unchanged) ---")
        try:
            dto1 = await service.validate_match(match_id=1)
            print(f"Result: {dto1.status} at {dto1.kickoff_time}")
        except Exception as e:
            print(e)

        print("\n--- Validating Match 3 (SIMULATION: Should switch to DELAYED) ---")
        try:
            dto3 = await service.validate_match(match_id=3)
            print(f"Result: {dto3.status} at {dto3.kickoff_time}")
            print(f"Last Validated: {dto3.last_validated_at}")
        except Exception as e:
            print(e)


if __name__ == "__main__":
    asyncio.run(main())