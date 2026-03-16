from datetime import datetime
from app.database import get_db_ctx


def ha_estrazione_oggi(lotteria: str) -> bool:
    oggi = datetime.now().strftime("%Y-%m-%d")
    ora_attuale = datetime.now().hour

    with get_db_ctx() as conn:
        if lotteria == "millionday":
            if ora_attuale >= 18:
                row = conn.execute(
                    "SELECT 1 FROM millionday WHERE data = ? AND ora >= '20:00' LIMIT 1",
                    (oggi,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT 1 FROM millionday WHERE data = ? AND ora < '18:00' LIMIT 1",
                    (oggi,)
                ).fetchone()

        elif lotteria == "superenalotto":
            row = conn.execute(
                "SELECT 1 FROM superenalotto WHERE data = ? LIMIT 1", (oggi,)
            ).fetchone()

        elif lotteria == "lotto":
            row = conn.execute(
                "SELECT 1 FROM lotto WHERE data = ? LIMIT 1", (oggi,)
            ).fetchone()

        elif lotteria == "10elotto":
            row = conn.execute(
                "SELECT 1 FROM diecelotto WHERE data = ? LIMIT 1", (oggi,)
            ).fetchone()

        elif lotteria == "vincicasa":
            row = conn.execute(
                "SELECT 1 FROM vincicasa WHERE data = ? LIMIT 1", (oggi,)
            ).fetchone()

        elif lotteria == "eurojackpot":
            row = conn.execute(
                "SELECT 1 FROM eurojackpot WHERE data = ? LIMIT 1", (oggi,)
            ).fetchone()

        elif lotteria == "sivincetutto":
            row = conn.execute(
                "SELECT 1 FROM sivincetutto WHERE data = ? LIMIT 1", (oggi,)
            ).fetchone()

        elif lotteria in ("winforlife_classico", "winforlife_grattacieli"):
            tipo = lotteria.replace("winforlife_", "")
            row = conn.execute(
                "SELECT 1 FROM winforlife WHERE data = ? AND tipo = ? LIMIT 1",
                (oggi, tipo)
            ).fetchone()

        else:
            return False

        return row is not None