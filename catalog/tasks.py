from celery import shared_task


@shared_task(
    name="catalog.add_numbers",
)
def add_numbers(first_number, second_number):
    return first_number + second_number
