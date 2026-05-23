import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/feed/feed_dto.dart';
import 'package:kpa_app/data/feed/feed_repository_impl.dart';
import 'package:kpa_app/domain/feed/feed_repository.dart';
import 'package:kpa_app/presentation/feed/feed_screen.dart';

class _FakeFeedRepo implements FeedRepository {
  _FakeFeedRepo(this.page);
  final FeedPageDto page;
  @override
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20}) async =>
      page;
}

Widget _wrap(Widget child, {required FeedRepository repo}) {
  return ProviderScope(
    overrides: [feedRepositoryProvider.overrideWithValue(repo)],
    child: MaterialApp(
      theme: ThemeData.light(useMaterial3: true),
      home: child,
    ),
  );
}

void main() {
  testWidgets('renders empty state when no items', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(
          const FeedPageDto(items: [], nextCursor: null),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining("We're still looking"), findsOneWidget);
  });

  testWidgets('renders feed item cards', (tester) async {
    final item = FeedItemDto(
      match: MatchSummaryDto(
        id: 'm1',
        totalScore: 0.8,
        scoreComponents: const {},
      ),
      job: JobSummaryDto(
        id: 'j1',
        title: 'Engineer',
        location: 'BLR',
        status: 'open',
        postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
    );
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(
          FeedPageDto(items: [item], nextCursor: null),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Engineer'), findsOneWidget);
    expect(find.text('Acme Co'), findsOneWidget);
    expect(find.text("You're all caught up"), findsOneWidget);
  });
}
