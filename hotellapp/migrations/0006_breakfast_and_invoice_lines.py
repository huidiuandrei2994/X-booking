from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('hotellapp', '0005_rateseason_apply_on'),
    ]

    operations = [
        # Reservation breakfast fields
        migrations.AddField(
            model_name='reservation',
            name='breakfast_included',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='reservation',
            name='breakfast_price',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=8),
        ),
        # Invoice legal fields
        migrations.AddField(
            model_name='invoice',
            name='series',
            field=models.CharField(default='XB', max_length=10),
        ),
        migrations.AddField(
            model_name='invoice',
            name='number',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='due_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='payment_method',
            field=models.CharField(choices=[('cash', 'Cash'), ('card', 'Card'), ('transfer', 'Bank Transfer')], default='cash', max_length=20),
        ),
        # InvoiceLine model
        migrations.CreateModel(
            name='InvoiceLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=200)),
                ('quantity', models.DecimalField(decimal_places=2, default=Decimal('1.00'), max_digits=8)),
                ('unit_price', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('vat_rate', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=4)),
                ('total_excl_vat', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('vat_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='hotellapp.invoice')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.AddConstraint(
            model_name='invoice',
            constraint=models.UniqueConstraint(fields=('series', 'number'), name='uniq_invoice_series_number'),
        ),
    ]
