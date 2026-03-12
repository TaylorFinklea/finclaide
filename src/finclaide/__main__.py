from finclaide.app import create_app


def main() -> None:
    app = create_app()
    app.run(host=app.config["FINCLAIDE_CONFIG"].host, port=app.config["FINCLAIDE_CONFIG"].port)


if __name__ == "__main__":
    main()
