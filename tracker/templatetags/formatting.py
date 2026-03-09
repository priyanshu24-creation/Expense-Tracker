from django import template

register = template.Library()


@register.filter
def currency(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 0.0
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    formatted = f"{amount:,.2f}"
    return f"{sign}₹{formatted}"
