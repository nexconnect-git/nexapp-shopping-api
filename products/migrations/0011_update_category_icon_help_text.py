from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0010_category_icon_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="icon_name",
            field=models.CharField(
                blank=True,
                help_text="Admin configured customer-app icon. Prefer an emoji; image URLs and Material icon names are also supported.",
                max_length=80,
            ),
        ),
    ]
