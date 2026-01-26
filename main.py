import uvicorn


def main() -> None:
    """
    Convenience entrypoint to run the FastAPI app with uvicorn.

    You can also run the app via:
      uvicorn app.main:app --reload
    """

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
