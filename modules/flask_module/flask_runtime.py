import logging
import threading
import time


logger = logging.getLogger("app")


def start_flask_app():
    """Start the Flask app in a daemon thread."""
    from modules.flask_module.fl_app import app as flask_app

    startup_error = {}

    def run_flask():
        try:
            flask_app.run(debug=False, host="127.0.0.1", port=5000, use_reloader=False)
        except Exception as e:
            startup_error["exception"] = e
            logger.error("Ошибка при запуске Flask: %s", e)
            raise

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    time.sleep(1)
    if "exception" in startup_error:
        raise RuntimeError("Flask startup failed.") from startup_error["exception"]
    if not flask_thread.is_alive():
        raise RuntimeError("Flask thread stopped during startup.")
    logger.info("Flask запущен на http://127.0.0.1:5000")
    return flask_thread
