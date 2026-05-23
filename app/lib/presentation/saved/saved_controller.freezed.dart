// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'saved_controller.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$SavedState {
  List<SavedJobListItemDto> get items;
  String? get cursor;
  bool get hasMore;
  bool get isLoadingMore;

  /// Create a copy of SavedState
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $SavedStateCopyWith<SavedState> get copyWith =>
      _$SavedStateCopyWithImpl<SavedState>(this as SavedState, _$identity);

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is SavedState &&
            const DeepCollectionEquality().equals(other.items, items) &&
            (identical(other.cursor, cursor) || other.cursor == cursor) &&
            (identical(other.hasMore, hasMore) || other.hasMore == hasMore) &&
            (identical(other.isLoadingMore, isLoadingMore) ||
                other.isLoadingMore == isLoadingMore));
  }

  @override
  int get hashCode => Object.hash(
      runtimeType,
      const DeepCollectionEquality().hash(items),
      cursor,
      hasMore,
      isLoadingMore);

  @override
  String toString() {
    return 'SavedState(items: $items, cursor: $cursor, hasMore: $hasMore, isLoadingMore: $isLoadingMore)';
  }
}

/// @nodoc
abstract mixin class $SavedStateCopyWith<$Res> {
  factory $SavedStateCopyWith(
          SavedState value, $Res Function(SavedState) _then) =
      _$SavedStateCopyWithImpl;
  @useResult
  $Res call(
      {List<SavedJobListItemDto> items,
      String? cursor,
      bool hasMore,
      bool isLoadingMore});
}

/// @nodoc
class _$SavedStateCopyWithImpl<$Res> implements $SavedStateCopyWith<$Res> {
  _$SavedStateCopyWithImpl(this._self, this._then);

  final SavedState _self;
  final $Res Function(SavedState) _then;

  /// Create a copy of SavedState
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? items = null,
    Object? cursor = freezed,
    Object? hasMore = null,
    Object? isLoadingMore = null,
  }) {
    return _then(_self.copyWith(
      items: null == items
          ? _self.items
          : items // ignore: cast_nullable_to_non_nullable
              as List<SavedJobListItemDto>,
      cursor: freezed == cursor
          ? _self.cursor
          : cursor // ignore: cast_nullable_to_non_nullable
              as String?,
      hasMore: null == hasMore
          ? _self.hasMore
          : hasMore // ignore: cast_nullable_to_non_nullable
              as bool,
      isLoadingMore: null == isLoadingMore
          ? _self.isLoadingMore
          : isLoadingMore // ignore: cast_nullable_to_non_nullable
              as bool,
    ));
  }
}

/// Adds pattern-matching-related methods to [SavedState].
extension SavedStatePatterns on SavedState {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_SavedState value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _SavedState() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_SavedState value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedState():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_SavedState value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedState() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(List<SavedJobListItemDto> items, String? cursor,
            bool hasMore, bool isLoadingMore)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _SavedState() when $default != null:
        return $default(
            _that.items, _that.cursor, _that.hasMore, _that.isLoadingMore);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(List<SavedJobListItemDto> items, String? cursor,
            bool hasMore, bool isLoadingMore)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedState():
        return $default(
            _that.items, _that.cursor, _that.hasMore, _that.isLoadingMore);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(List<SavedJobListItemDto> items, String? cursor,
            bool hasMore, bool isLoadingMore)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SavedState() when $default != null:
        return $default(
            _that.items, _that.cursor, _that.hasMore, _that.isLoadingMore);
      case _:
        return null;
    }
  }
}

/// @nodoc

class _SavedState implements SavedState {
  const _SavedState(
      {required final List<SavedJobListItemDto> items,
      required this.cursor,
      required this.hasMore,
      this.isLoadingMore = false})
      : _items = items;

  final List<SavedJobListItemDto> _items;
  @override
  List<SavedJobListItemDto> get items {
    if (_items is EqualUnmodifiableListView) return _items;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_items);
  }

  @override
  final String? cursor;
  @override
  final bool hasMore;
  @override
  @JsonKey()
  final bool isLoadingMore;

  /// Create a copy of SavedState
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$SavedStateCopyWith<_SavedState> get copyWith =>
      __$SavedStateCopyWithImpl<_SavedState>(this, _$identity);

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _SavedState &&
            const DeepCollectionEquality().equals(other._items, _items) &&
            (identical(other.cursor, cursor) || other.cursor == cursor) &&
            (identical(other.hasMore, hasMore) || other.hasMore == hasMore) &&
            (identical(other.isLoadingMore, isLoadingMore) ||
                other.isLoadingMore == isLoadingMore));
  }

  @override
  int get hashCode => Object.hash(
      runtimeType,
      const DeepCollectionEquality().hash(_items),
      cursor,
      hasMore,
      isLoadingMore);

  @override
  String toString() {
    return 'SavedState(items: $items, cursor: $cursor, hasMore: $hasMore, isLoadingMore: $isLoadingMore)';
  }
}

/// @nodoc
abstract mixin class _$SavedStateCopyWith<$Res>
    implements $SavedStateCopyWith<$Res> {
  factory _$SavedStateCopyWith(
          _SavedState value, $Res Function(_SavedState) _then) =
      __$SavedStateCopyWithImpl;
  @override
  @useResult
  $Res call(
      {List<SavedJobListItemDto> items,
      String? cursor,
      bool hasMore,
      bool isLoadingMore});
}

/// @nodoc
class __$SavedStateCopyWithImpl<$Res> implements _$SavedStateCopyWith<$Res> {
  __$SavedStateCopyWithImpl(this._self, this._then);

  final _SavedState _self;
  final $Res Function(_SavedState) _then;

  /// Create a copy of SavedState
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? items = null,
    Object? cursor = freezed,
    Object? hasMore = null,
    Object? isLoadingMore = null,
  }) {
    return _then(_SavedState(
      items: null == items
          ? _self._items
          : items // ignore: cast_nullable_to_non_nullable
              as List<SavedJobListItemDto>,
      cursor: freezed == cursor
          ? _self.cursor
          : cursor // ignore: cast_nullable_to_non_nullable
              as String?,
      hasMore: null == hasMore
          ? _self.hasMore
          : hasMore // ignore: cast_nullable_to_non_nullable
              as bool,
      isLoadingMore: null == isLoadingMore
          ? _self.isLoadingMore
          : isLoadingMore // ignore: cast_nullable_to_non_nullable
              as bool,
    ));
  }
}

// dart format on
