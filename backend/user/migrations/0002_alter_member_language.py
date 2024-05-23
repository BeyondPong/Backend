# Generated by Django 3.2.13 on 2024-05-23 05:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='member',
            name='language',
            field=models.CharField(choices=[('en', 'English'), ('ko', 'Korean'), ('jp', 'Japanese')], default='en', max_length=2),
        ),
    ]