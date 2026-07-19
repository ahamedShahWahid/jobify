import 'package:jobify_app/data/feed/feed_dto.dart';
import 'package:jobify_app/data/feed/feed_repository_impl.dart';
import 'package:jobify_app/data/feed/match_feedback_rating.dart';
import 'package:jobify_app/data/jobs/jobs_repository_impl.dart';
import 'package:jobify_app/presentation/paging/paged_state.dart';
import 'package:jobify_app/presentation/paging/paging.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'feed_controller.g.dart';

typedef FeedState = PagedState<FeedItemDto>;

@riverpod
class FeedController extends _$FeedController {
  @override
  Future<FeedState> build() async {
    final page = await ref.read(feedRepositoryProvider).fetchPage();
    return PagedState(
      items: page.items,
      cursor: page.nextCursor,
      hasMore: page.nextCursor != null,
    );
  }

  Future<void> refresh() async {
    ref.invalidateSelf();
    await future;
  }

  Future<void> loadMore() => loadNextPage<FeedItemDto>(
        currentState: state,
        fetch: ({String? cursor}) async {
          final page =
              await ref.read(feedRepositoryProvider).fetchPage(cursor: cursor);
          return PagedState(
            items: page.items,
            cursor: page.nextCursor,
            hasMore: page.nextCursor != null,
          );
        },
        setState: (s) => state = s,
      );

  /// Optimistic thumbs-down: remove the card immediately, roll back on error.
  Future<void> rateDown(String jobId) async {
    final prev = state;
    final s = state.value;
    if (s != null) {
      state = AsyncData(
        s.copyWith(
          items: [
            for (final it in s.items)
              if (it.job.id != jobId) it,
          ],
        ),
      );
    }
    try {
      await ref
          .read(jobsRepositoryProvider)
          .rateMatch(jobId, MatchFeedbackRating.down);
    } catch (_) {
      state = prev; // restore — the card comes back
      rethrow;
    }
  }

  /// Thumbs-up: persist, then patch the item in place (card stays).
  Future<void> rateUp(String jobId) async {
    await ref
        .read(jobsRepositoryProvider)
        .rateMatch(jobId, MatchFeedbackRating.up);
    final s = state.value;
    if (s == null) return;
    state = AsyncData(
      s.copyWith(
        items: [
          for (final it in s.items)
            if (it.job.id != jobId)
              it
            else
              FeedItemDto(
                match: MatchSummaryDto(
                  id: it.match.id,
                  totalScore: it.match.totalScore,
                  scoreComponents: it.match.scoreComponents,
                  explanation: it.match.explanation,
                  surfacedAt: it.match.surfacedAt,
                  myFeedback: MatchFeedbackRating.up,
                ),
                job: it.job,
                employer: it.employer,
              ),
        ],
      ),
    );
  }

  /// Undo a thumbs-down: clear the rating server-side, refetch page 1.
  Future<void> undoDown(String jobId) async {
    await ref.read(jobsRepositoryProvider).clearMatchFeedback(jobId);
    await refresh();
  }
}
