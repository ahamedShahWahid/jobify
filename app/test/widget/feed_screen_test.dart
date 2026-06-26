import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/feed_repository.dart';
import 'package:jobify_app/data/feed/feed_repository_impl.dart';
import 'package:jobify_app/data/feed/match_generator.dart';
import 'package:jobify_app/data/jobs/job_status.dart';
import 'package:jobify_app/presentation/feed/feed_item_card.dart';
import 'package:jobify_app/presentation/feed/feed_screen.dart';

class _FakeFeedRepo implements FeedRepository {
  _FakeFeedRepo(this.page);
  final FeedPageDto page;
  @override
  Future<FeedPageDto> fetchPage({String? cursor, int limit = 20}) async => page;
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

FeedItemDto _cardItem({String? caveat}) => FeedItemDto(
      match: MatchSummaryDto(
        id: 'm1',
        totalScore: 0.85,
        scoreComponents: const {},
        explanation: ExplanationDto(
          fit: 'Your Django work lines up.',
          generator: MatchGenerator.templated,
          generatorVersion: '1',
          caveat: caveat,
        ),
      ),
      job: JobSummaryDto(
        id: 'j1',
        title: 'Backend Engineer',
        locations: const ['BLR'],
        status: JobStatus.open,
        postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
    );

Widget _wrapCard(FeedItemDto item) => MediaQuery(
      data: const MediaQueryData(disableAnimations: true),
      child: MaterialApp(
        theme: ThemeData.light(useMaterial3: true),
        home: Scaffold(
          body: FeedItemCard(
            job: item.job,
            employer: item.employer,
            match: item.match,
            explanation: item.match.explanation,
            onTap: () {},
          ),
        ),
      ),
    );

void main() {
  testWidgets('renders empty state when no items', (tester) async {
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(
          const FeedPageDto(items: []),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining("We're still looking"), findsOneWidget);
  });

  testWidgets('renders feed item cards', (tester) async {
    final item = FeedItemDto(
      match: const MatchSummaryDto(
        id: 'm1',
        totalScore: 0.8,
        scoreComponents: {},
      ),
      job: JobSummaryDto(
        id: 'j1',
        title: 'Engineer',
        locations: const ['BLR'],
        status: JobStatus.open,
        postedAt: DateTime.parse('2026-05-18T00:00:00Z'),
      ),
      employer: const EmployerSummaryDto(id: 'e1', name: 'Acme Co'),
    );
    await tester.pumpWidget(
      _wrap(
        const FeedScreen(),
        repo: _FakeFeedRepo(
          FeedPageDto(items: [item]),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Engineer'), findsOneWidget);
    expect(find.text('ACME CO'), findsOneWidget);
    expect(find.text("You're all caught up"), findsOneWidget);
  });

  testWidgets('card leads with the match sentence and shows the caveat',
      (tester) async {
    await tester.pumpWidget(
      _wrapCard(_cardItem(caveat: '3 yrs vs 5 required')),
    );
    await tester.pumpAndSettle();
    expect(find.text('Your Django work lines up.'), findsOneWidget);
    expect(find.textContaining('3 yrs vs 5 required'), findsOneWidget);
  });

  testWidgets('no caveat line when caveat is null', (tester) async {
    await tester.pumpWidget(_wrapCard(_cardItem()));
    await tester.pumpAndSettle();
    expect(find.text('Your Django work lines up.'), findsOneWidget);
    expect(find.textContaining('vs'), findsNothing);
  });
}
