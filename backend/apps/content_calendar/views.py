import calendar
import datetime

from django.http import Http404, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.companies.models import Company
from common.permissions import IsAdmin

from . import excel
from .models import ContentCalendarItem
from .serializers import ContentCalendarItemSerializer, ExcelUploadSerializer


class CompanyScopedMixin:
    """Resolves the company from the URL, 404ing if a client tries to reach a company that isn't theirs."""

    def get_company(self):
        company = generics.get_object_or_404(Company, pk=self.kwargs['company_id'])
        user = self.request.user
        if not user.is_admin:
            profile = getattr(user, 'client_profile', None)
            if not profile or profile.company_id != company.id:
                raise Http404
        return company


def _serialize_row(entry):
    data = dict(entry['data'])
    if data.get('scheduled_date'):
        data['scheduled_date'] = data['scheduled_date'].isoformat()
    if data.get('scheduled_time'):
        data['scheduled_time'] = data['scheduled_time'].isoformat()
    result = {'row': entry['row'], 'data': data}
    if 'errors' in entry:
        result['errors'] = entry['errors']
    return result


class CalendarPagination(PageNumberPagination):
    """A month of content rarely exceeds this, so the calendar view gets it all in one page."""

    page_size = 200


class ContentCalendarItemListCreateView(CompanyScopedMixin, generics.ListCreateAPIView):
    """List a company's content calendar, or manually add an item (Epic 04: Calendar Management)."""

    serializer_class = ContentCalendarItemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CalendarPagination

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not (
            request.user.is_authenticated and request.user.is_admin
        ):
            self.permission_denied(request, message='Only admins can edit the content calendar.')

    def get_queryset(self):
        company = self.get_company()
        queryset = ContentCalendarItem.objects.filter(company=company)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        platform = self.request.query_params.get('platform')
        if platform:
            queryset = queryset.filter(platforms__contains=[platform])

        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(topic__icontains=search)

        month_param = self.request.query_params.get('month')
        if month_param:
            try:
                year, month = (int(part) for part in month_param.split('-', 1))
                _, last_day = calendar.monthrange(year, month)
                queryset = queryset.filter(
                    scheduled_date__gte=datetime.date(year, month, 1),
                    scheduled_date__lte=datetime.date(year, month, last_day),
                )
            except (ValueError, TypeError):
                pass

        return queryset

    def perform_create(self, serializer):
        serializer.save(
            company=self.get_company(),
            created_by=self.request.user,
            source=ContentCalendarItem.Source.MANUAL,
        )


class ContentCalendarItemDetailView(CompanyScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    """View, edit, or delete a single calendar item."""

    serializer_class = ContentCalendarItemSerializer
    permission_classes = [IsAuthenticated]

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not (
            request.user.is_authenticated and request.user.is_admin
        ):
            self.permission_denied(request, message='Only admins can edit the content calendar.')

    def get_queryset(self):
        return ContentCalendarItem.objects.filter(company=self.get_company())


class ContentCalendarDuplicateView(CompanyScopedMixin, APIView):
    """Admin: duplicate a single calendar item as a new draft (Epic 04: Duplicate calendar)."""

    permission_classes = [IsAdmin]
    serializer_class = ContentCalendarItemSerializer

    def post(self, request, company_id, pk):
        company = self.get_company()
        item = generics.get_object_or_404(ContentCalendarItem, pk=pk, company=company)
        item.pk = None
        item._state.adding = True
        item.status = ContentCalendarItem.Status.DRAFT
        item.source = ContentCalendarItem.Source.MANUAL
        item.created_by = request.user
        item.save()
        return Response(ContentCalendarItemSerializer(item).data, status=status.HTTP_201_CREATED)


class ContentCalendarTemplateView(APIView):
    """Admin: download a blank Excel template for the content calendar (Epic 04: Excel template)."""

    permission_classes = [IsAdmin]

    @extend_schema(responses={200: OpenApiTypes.BINARY})
    def get(self, request, company_id):
        buffer = excel.build_template_workbook()
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="content_calendar_template.xlsx"'
        return response


class ContentCalendarImportPreviewView(CompanyScopedMixin, APIView):
    """Admin: parse and validate an uploaded Excel file without saving anything (Epic 04: Import preview)."""

    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = ExcelUploadSerializer

    def post(self, request, company_id):
        self.get_company()
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            valid_rows, invalid_rows = excel.parse_and_validate(upload)
        except excel.WorkbookParseError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'valid_count': len(valid_rows),
            'invalid_count': len(invalid_rows),
            'valid_rows': [_serialize_row(r) for r in valid_rows],
            'invalid_rows': [_serialize_row(r) for r in invalid_rows],
        })


class ContentCalendarImportCommitView(CompanyScopedMixin, APIView):
    """Admin: parse an uploaded Excel file and create calendar items for every valid row."""

    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = ExcelUploadSerializer

    def post(self, request, company_id):
        company = self.get_company()
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            valid_rows, invalid_rows = excel.parse_and_validate(upload)
        except excel.WorkbookParseError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        created_items = [
            ContentCalendarItem.objects.create(
                company=company,
                created_by=request.user,
                source=ContentCalendarItem.Source.EXCEL_IMPORT,
                **entry['data'],
            )
            for entry in valid_rows
        ]

        return Response({
            'created_count': len(created_items),
            'invalid_count': len(invalid_rows),
            'invalid_rows': [_serialize_row(r) for r in invalid_rows],
        }, status=status.HTTP_201_CREATED)
