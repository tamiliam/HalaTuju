"""The course and institution lists and detail pages."""
import json

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Course, CourseRequirement, Institution
from ..serializers import (
    CourseRequirementSerializer,
    CourseSerializer,
    InstitutionSerializer,
    MascoOccupationSerializer,
)


class CourseListView(APIView):
    """GET /api/v1/courses/ - List all courses with optional pagination."""
    permission_classes = [AllowAny]

    def get(self, request):
        courses = Course.objects.all()

        # Optional pagination (backwards-compatible: no params = all results)
        page = request.query_params.get('page')
        page_size = min(int(request.query_params.get('page_size', 50)), 100)

        if page is not None:
            try:
                page = max(int(page), 1)
            except (ValueError, TypeError):
                page = 1
            start = (page - 1) * page_size
            total = courses.count()
            courses = courses[start:start + page_size]
            serializer = CourseSerializer(courses, many=True)
            return Response({
                'courses': serializer.data,
                'total_count': total,
                'page': page,
                'page_size': page_size,
            })

        serializer = CourseSerializer(courses, many=True)
        return Response({
            'courses': serializer.data,
            'total_count': len(serializer.data),
        })


class CourseDetailView(APIView):
    """GET /api/v1/courses/<course_id>/ - Course detail with institutions."""
    permission_classes = [AllowAny]

    def get(self, request, course_id):
        from ..models import CourseInstitution

        try:
            course = Course.objects.get(course_id=course_id)
            course_data = CourseSerializer(course).data

            # Get institutions offering this course, with per-offering details
            links = CourseInstitution.objects.filter(
                course_id=course_id
            ).select_related('institution')

            institutions = []
            for link in links:
                if not link.institution:
                    continue
                inst_data = InstitutionSerializer(link.institution).data
                # Add per-offering details from CourseInstitution
                inst_data['hyperlink'] = link.hyperlink or ''
                inst_data['tuition_fee_semester'] = link.tuition_fee_semester or ''
                inst_data['hostel_fee_semester'] = link.hostel_fee_semester or ''
                inst_data['registration_fee'] = link.registration_fee or ''
                inst_data['monthly_allowance'] = float(link.monthly_allowance) if link.monthly_allowance else None
                inst_data['practical_allowance'] = float(link.practical_allowance) if link.practical_allowance else None
                inst_data['free_hostel'] = link.free_hostel
                inst_data['free_meals'] = link.free_meals
                institutions.append(inst_data)

            # Get career occupations linked to this course
            career_occupations = MascoOccupationSerializer(
                course.career_occupations.all(), many=True
            ).data

            # Get requirements from CourseRequirement
            requirements = None
            merit_cutoff = None
            merit_type = 'standard'
            try:
                req = CourseRequirement.objects.get(course_id=course_id)
                requirements = CourseRequirementSerializer(req).data
                if req.merit_cutoff:
                    merit_cutoff = req.merit_cutoff
                merit_type = req.merit_type or 'standard'

                # PISMP: find paired language variants for this programme
                # e.g. if viewing Chinese-medium (03), also check Tamil-medium (04)
                if req.source_type == 'pismp':
                    zone = course_id[4:6] if len(course_id) >= 6 else ''
                    if zone in ('03', '04'):
                        # Find all zone variants of the same programme name
                        nat_req = CourseRequirement.objects.filter(
                            source_type='pismp',
                            course__course=course.course,
                        ).exclude(course_id=course_id)
                        # Get National hash to compare
                        nat_hash = None
                        for nr in nat_req:
                            nz = nr.course_id[4:6] if len(nr.course_id) >= 6 else ''
                            if nz in ('01', '06'):
                                nat_hash = json.dumps(
                                    nr.subject_group_req, sort_keys=True
                                ) if nr.subject_group_req else 'null'
                                break
                        my_hash = json.dumps(
                            req.subject_group_req, sort_keys=True
                        ) if req.subject_group_req else 'null'
                        # Only add languages if this variant differs from National
                        if my_hash != nat_hash:
                            langs = []
                            # Check all zone variants for language differences
                            for nr in nat_req:
                                nz = nr.course_id[4:6] if len(nr.course_id) >= 6 else ''
                                nr_hash = json.dumps(
                                    nr.subject_group_req, sort_keys=True
                                ) if nr.subject_group_req else 'null'
                                if nz == '03' and nr_hash != nat_hash:
                                    langs.append('Bahasa Cina')
                                elif nz == '04' and nr_hash != nat_hash:
                                    langs.append('Bahasa Tamil')
                            # Include self
                            if zone == '03' and 'Bahasa Cina' not in langs:
                                langs.append('Bahasa Cina')
                            if zone == '04' and 'Bahasa Tamil' not in langs:
                                langs.append('Bahasa Tamil')
                            if langs:
                                requirements['pismp_languages'] = sorted(langs)
            except CourseRequirement.DoesNotExist:
                pass

            response_data = {
                'course': course_data,
                'institutions': institutions,
                'career_occupations': career_occupations,
                'requirements': requirements,
            }
            if merit_cutoff is not None:
                response_data['merit_cutoff'] = merit_cutoff
            if merit_type != 'standard':
                response_data['merit_type'] = merit_type

            return Response(response_data)
        except Course.DoesNotExist:
            return Response(
                {'error': 'Course not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class InstitutionListView(APIView):
    """GET /api/v1/institutions/ - List all institutions."""
    permission_classes = [AllowAny]

    def get(self, request):
        # Filter by state if provided
        state = request.query_params.get('state')
        qs = Institution.objects.all()
        if state:
            qs = qs.filter(state__iexact=state)

        serializer = InstitutionSerializer(qs, many=True)
        return Response({
            'institutions': serializer.data,
            'total_count': len(serializer.data),
        })


class InstitutionDetailView(APIView):
    """GET /api/v1/institutions/<id>/ - Institution detail."""
    permission_classes = [AllowAny]

    def get(self, request, institution_id):
        try:
            institution = Institution.objects.get(institution_id=institution_id)
            serializer = InstitutionSerializer(institution)
            return Response(serializer.data)
        except Institution.DoesNotExist:
            return Response(
                {'error': 'Institution not found'},
                status=status.HTTP_404_NOT_FOUND
            )
