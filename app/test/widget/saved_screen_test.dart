import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/data/jobs/jobs_dto.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository.dart';
import 'package:jobify_app/data/jobs/saved_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/saved/saved_screen.dart';

class _FakeRepo implements SavedJobsRepository {
  _FakeRepo(this.page);
  final SavedJobsPageDto page;
  @override
  Future<SavedJobsPageDto> fetchPage({
    String? cursor,
    int limit = 20,
  }) async =>
      page;
}

Widget _wrap(Widget child, {required SavedJobsRepository repo}) =>
    ProviderScope(
      overrides: [savedJobsRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: child,
      ),
    );

void main() {
  testWidgets('empty state', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const SavedScreen(),
        repo: _FakeRepo(
          const SavedJobsPageDto(items: []),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Nothing saved yet'), findsOneWidget);
  });

  testWidgets('renders open + closed jobs differently', (tester) async {
    final items = [
      SavedJobListItemDto(
        saved: SavedJobDto(
          id: 's1',
          jobId: 'j1',
          createdAt: DateTime(2026, 5),
        ),
        job: JobSummaryDto(
          id: 'j1',
          title: 'Open Eng',
          locations: const ['BLR'],
          status: JobStatus.open,
          postedAt: DateTime(2026, 5),
        ),
        employer: const EmployerSummaryDto(id: 'e1', name: 'Acme'),
        match: const MatchSummaryDto(
          id: 'm1',
          totalScore: 0.8,
          scoreComponents: {},
        ),
      ),
      SavedJobListItemDto(
        saved: SavedJobDto(
          id: 's2',
          jobId: 'j2',
          createdAt: DateTime(2026, 5, 2),
        ),
        job: JobSummaryDto(
          id: 'j2',
          title: 'Closed Eng',
          locations: const ['BLR'],
          status: JobStatus.closed,
          postedAt: DateTime(2026, 5),
        ),
        employer: const EmployerSummaryDto(id: 'e2', name: 'Beta'),
      ),
    ];
    await tester.pumpWidget(
      _wrap(
        const SavedScreen(),
        repo: _FakeRepo(
          SavedJobsPageDto(items: items),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Open Eng'), findsOneWidget);
    expect(find.text('Closed Eng'), findsOneWidget);
    expect(find.text('Closed'), findsOneWidget);
  });
}
