# Generated by Django 4.2.6 on 2024-05-28 18:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("passport_admin", "0001_squashed_0003_remove_passportbanner_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="passportbanner",
            name="application",
            field=models.CharField(
                choices=[("passport", "Passport"), ("id_staking_v2", "ID Staking V2")],
                default="passport",
                max_length=50,
            ),
        ),
    ]