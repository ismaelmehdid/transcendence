# Generated by Django 4.2.5 on 2024-12-10 18:30

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_alter_user_last_activity'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='last_activity',
        ),
    ]