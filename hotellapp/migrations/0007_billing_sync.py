from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotellapp', '0006_breakfast_and_invoice_lines'),
    ]

    operations = [
        # Client billing fields
        migrations.AddField(
            model_name='client',
            name='billing_type',
            field=models.CharField(choices=[('individual', 'Individual'), ('company', 'Company')], default='individual', max_length=20),
        ),
        migrations.AddField(
            model_name='client',
            name='company_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='client',
            name='company_tax_id',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Tax ID (CUI/CIF)'),
        ),
        migrations.AddField(
            model_name='client',
            name='company_vat_payer',
            field=models.BooleanField(default=False),
        ),

        # Invoice billing snapshot and lock
        migrations.AddField(
            model_name='invoice',
            name='billing_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='billing_tax_id',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='billing_address',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='locked',
            field=models.BooleanField(default=False),
        ),
    ]
