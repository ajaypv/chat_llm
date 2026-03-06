import asyncio

from chat_app.rag_tool import semantic_search_raw


async def _main() -> None:
    print("\n=== categories=['osm'] ===")
    out = await semantic_search_raw(
        query="What is OSM?",
        top_k=10,
        categories=["osm"],
        request_id="probe",
    )
    print(out)

    print("\n=== categories=['deployment','general','osm'] ===")
    out = await semantic_search_raw(
        query="What is OSM?",
        top_k=10,
        categories=["deployment", "general", "osm"],
        request_id="probe",
    )
    print(out)

    print("\n=== categories=['deployment'] ===")
    out = await semantic_search_raw(
        query="What is OSM?",
        top_k=10,
        categories=["deployment"],
        request_id="probe",
    )
    print(out)


if __name__ == "__main__":
    asyncio.run(_main())
