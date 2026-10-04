from rest_framework import serializers

from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    company_name = serializers.SerializerMethodField()
    formats = serializers.SerializerMethodField()
    generated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id', 'company', 'company_name', 'report_type', 'report_type_display', 'title', 'period_start',
            'period_end', 'status', 'status_display', 'error', 'formats', 'is_automated', 'generated_at',
            'emailed_at', 'whatsapp_sent_at', 'generated_by', 'generated_by_name', 'created_at',
        ]
        read_only_fields = fields

    def get_company_name(self, obj) -> str:
        return obj.company.name if obj.company else 'All companies'

    def get_formats(self, obj) -> list:
        return [fmt for fmt, field in (('pdf', obj.pdf_file), ('xlsx', obj.xlsx_file), ('csv', obj.csv_file)) if field]

    def get_generated_by_name(self, obj) -> str:
        if obj.is_automated:
            return 'Automatic'
        return obj.generated_by.get_full_name() if obj.generated_by else ''


class ReportDetailSerializer(ReportSerializer):
    class Meta(ReportSerializer.Meta):
        fields = [*ReportSerializer.Meta.fields, 'data']
        read_only_fields = fields


class ReportCreateSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=Report.ReportType.choices)
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    title = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        if attrs['period_end'] < attrs['period_start']:
            raise serializers.ValidationError({'period_end': 'The end date cannot be before the start date.'})
        if (attrs['period_end'] - attrs['period_start']).days > 400:
            raise serializers.ValidationError({'period_end': 'Reports can cover at most about 13 months.'})
        return attrs
