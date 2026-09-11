from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def ui(context, english, filipino):
    request = context.get('request')
    return filipino if request and request.COOKIES.get('calamansense_language') == 'fil' else english
