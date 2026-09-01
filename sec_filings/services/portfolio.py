from sec_filings.db.models import Portfolio

DEFAULT_PORTFOLIO = "Watchlist"


def get_or_create_default_portfolio(session) -> Portfolio:
    portfolio = session.query(Portfolio).filter_by(name=DEFAULT_PORTFOLIO).one_or_none()
    if portfolio is None:
        portfolio = Portfolio(
            name=DEFAULT_PORTFOLIO,
            description="Default SEC filings watchlist",
        )
        session.add(portfolio)
        session.commit()
    return portfolio
