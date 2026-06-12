import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/jobs/application_source.dart';
import 'package:jobify_app/data/jobs/application_status.dart';
import 'package:jobify_app/data/jobs/applications_repository_impl.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/applications_repository.dart';
import 'package:jobify_app/presentation/applications/applications_screen.dart';

class _FakeRepo implements ApplicationsRepository {
  _FakeRepo(this.page);
  final ApplicationsPageDto page;
  @override
  Future<ApplicationsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      page;
  @override
  Future<ApplicationDto> withdraw(String id) async =>
      throw UnimplementedError();
}

Widget _wrap(Widget child, {required ApplicationsRepository repo}) =>
    ProviderScope(
      overrides: [applicationsRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: child,
      ),
    );

void main() {
  testWidgets('empty state', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const ApplicationsScreen(),
        repo: _FakeRepo(
          const ApplicationsPageDto(items: [], nextCursor: null),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('No applications yet'), findsOneWidget);
  });

  testWidgets('renders applied + withdrawn rows', (tester) async {
    final items = [
      ApplicationListItemDto(
        application: ApplicationDto(
          id: 'a1',
          jobId: 'j1',
          status: ApplicationStatus.applied,
          source: ApplicationSource.feed,
          createdAt: DateTime(2026, 5, 1),
          updatedAt: DateTime(2026, 5, 1),
        ),
        job: JobSummaryDto(
          id: 'j1',
          title: 'Eng',
          locations: const ['BLR'],
          status: JobStatus.open,
          postedAt: DateTime(2026, 4, 1),
        ),
        employer: const EmployerSummaryDto(id: 'e1', name: 'Acme'),
      ),
      ApplicationListItemDto(
        application: ApplicationDto(
          id: 'a2',
          jobId: 'j2',
          status: ApplicationStatus.withdrawn,
          source: ApplicationSource.feed,
          createdAt: DateTime(2026, 4, 20),
          updatedAt: DateTime(2026, 5, 5),
        ),
        job: JobSummaryDto(
          id: 'j2',
          title: 'Designer',
          locations: const ['BLR'],
          status: JobStatus.open,
          postedAt: DateTime(2026, 4, 1),
        ),
        employer: const EmployerSummaryDto(id: 'e2', name: 'Beta'),
      ),
    ];
    await tester.pumpWidget(
      _wrap(
        const ApplicationsScreen(),
        repo: _FakeRepo(
          ApplicationsPageDto(items: items, nextCursor: null),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Applied'), findsOneWidget);
    expect(find.text('Withdrawn'), findsOneWidget);
    expect(find.text('Eng'), findsOneWidget);
    expect(find.text('Designer'), findsOneWidget);
  });
}
