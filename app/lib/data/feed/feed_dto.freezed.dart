// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'feed_dto.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$FeedPageDto {
  List<FeedItemDto> get items;
  String? get nextCursor;

  /// Create a copy of FeedPageDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $FeedPageDtoCopyWith<FeedPageDto> get copyWith =>
      _$FeedPageDtoCopyWithImpl<FeedPageDto>(this as FeedPageDto, _$identity);

  /// Serializes this FeedPageDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is FeedPageDto &&
            const DeepCollectionEquality().equals(other.items, items) &&
            (identical(other.nextCursor, nextCursor) ||
                other.nextCursor == nextCursor));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
      runtimeType, const DeepCollectionEquality().hash(items), nextCursor);

  @override
  String toString() {
    return 'FeedPageDto(items: $items, nextCursor: $nextCursor)';
  }
}

/// @nodoc
abstract mixin class $FeedPageDtoCopyWith<$Res> {
  factory $FeedPageDtoCopyWith(
          FeedPageDto value, $Res Function(FeedPageDto) _then) =
      _$FeedPageDtoCopyWithImpl;
  @useResult
  $Res call({List<FeedItemDto> items, String? nextCursor});
}

/// @nodoc
class _$FeedPageDtoCopyWithImpl<$Res> implements $FeedPageDtoCopyWith<$Res> {
  _$FeedPageDtoCopyWithImpl(this._self, this._then);

  final FeedPageDto _self;
  final $Res Function(FeedPageDto) _then;

  /// Create a copy of FeedPageDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? items = null,
    Object? nextCursor = freezed,
  }) {
    return _then(_self.copyWith(
      items: null == items
          ? _self.items
          : items // ignore: cast_nullable_to_non_nullable
              as List<FeedItemDto>,
      nextCursor: freezed == nextCursor
          ? _self.nextCursor
          : nextCursor // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// Adds pattern-matching-related methods to [FeedPageDto].
extension FeedPageDtoPatterns on FeedPageDto {
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
    TResult Function(_FeedPageDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _FeedPageDto() when $default != null:
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
    TResult Function(_FeedPageDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _FeedPageDto():
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
    TResult? Function(_FeedPageDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _FeedPageDto() when $default != null:
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
    TResult Function(List<FeedItemDto> items, String? nextCursor)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _FeedPageDto() when $default != null:
        return $default(_that.items, _that.nextCursor);
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
    TResult Function(List<FeedItemDto> items, String? nextCursor) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _FeedPageDto():
        return $default(_that.items, _that.nextCursor);
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
    TResult? Function(List<FeedItemDto> items, String? nextCursor)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _FeedPageDto() when $default != null:
        return $default(_that.items, _that.nextCursor);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _FeedPageDto implements FeedPageDto {
  const _FeedPageDto({required final List<FeedItemDto> items, this.nextCursor})
      : _items = items;
  factory _FeedPageDto.fromJson(Map<String, dynamic> json) =>
      _$FeedPageDtoFromJson(json);

  final List<FeedItemDto> _items;
  @override
  List<FeedItemDto> get items {
    if (_items is EqualUnmodifiableListView) return _items;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableListView(_items);
  }

  @override
  final String? nextCursor;

  /// Create a copy of FeedPageDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$FeedPageDtoCopyWith<_FeedPageDto> get copyWith =>
      __$FeedPageDtoCopyWithImpl<_FeedPageDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$FeedPageDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _FeedPageDto &&
            const DeepCollectionEquality().equals(other._items, _items) &&
            (identical(other.nextCursor, nextCursor) ||
                other.nextCursor == nextCursor));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
      runtimeType, const DeepCollectionEquality().hash(_items), nextCursor);

  @override
  String toString() {
    return 'FeedPageDto(items: $items, nextCursor: $nextCursor)';
  }
}

/// @nodoc
abstract mixin class _$FeedPageDtoCopyWith<$Res>
    implements $FeedPageDtoCopyWith<$Res> {
  factory _$FeedPageDtoCopyWith(
          _FeedPageDto value, $Res Function(_FeedPageDto) _then) =
      __$FeedPageDtoCopyWithImpl;
  @override
  @useResult
  $Res call({List<FeedItemDto> items, String? nextCursor});
}

/// @nodoc
class __$FeedPageDtoCopyWithImpl<$Res> implements _$FeedPageDtoCopyWith<$Res> {
  __$FeedPageDtoCopyWithImpl(this._self, this._then);

  final _FeedPageDto _self;
  final $Res Function(_FeedPageDto) _then;

  /// Create a copy of FeedPageDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? items = null,
    Object? nextCursor = freezed,
  }) {
    return _then(_FeedPageDto(
      items: null == items
          ? _self._items
          : items // ignore: cast_nullable_to_non_nullable
              as List<FeedItemDto>,
      nextCursor: freezed == nextCursor
          ? _self.nextCursor
          : nextCursor // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// @nodoc
mixin _$FeedItemDto {
  MatchSummaryDto get match;
  JobSummaryDto get job;
  EmployerSummaryDto get employer;

  /// Create a copy of FeedItemDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $FeedItemDtoCopyWith<FeedItemDto> get copyWith =>
      _$FeedItemDtoCopyWithImpl<FeedItemDto>(this as FeedItemDto, _$identity);

  /// Serializes this FeedItemDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is FeedItemDto &&
            (identical(other.match, match) || other.match == match) &&
            (identical(other.job, job) || other.job == job) &&
            (identical(other.employer, employer) ||
                other.employer == employer));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, match, job, employer);

  @override
  String toString() {
    return 'FeedItemDto(match: $match, job: $job, employer: $employer)';
  }
}

/// @nodoc
abstract mixin class $FeedItemDtoCopyWith<$Res> {
  factory $FeedItemDtoCopyWith(
          FeedItemDto value, $Res Function(FeedItemDto) _then) =
      _$FeedItemDtoCopyWithImpl;
  @useResult
  $Res call(
      {MatchSummaryDto match, JobSummaryDto job, EmployerSummaryDto employer});

  $MatchSummaryDtoCopyWith<$Res> get match;
  $JobSummaryDtoCopyWith<$Res> get job;
  $EmployerSummaryDtoCopyWith<$Res> get employer;
}

/// @nodoc
class _$FeedItemDtoCopyWithImpl<$Res> implements $FeedItemDtoCopyWith<$Res> {
  _$FeedItemDtoCopyWithImpl(this._self, this._then);

  final FeedItemDto _self;
  final $Res Function(FeedItemDto) _then;

  /// Create a copy of FeedItemDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? match = null,
    Object? job = null,
    Object? employer = null,
  }) {
    return _then(_self.copyWith(
      match: null == match
          ? _self.match
          : match // ignore: cast_nullable_to_non_nullable
              as MatchSummaryDto,
      job: null == job
          ? _self.job
          : job // ignore: cast_nullable_to_non_nullable
              as JobSummaryDto,
      employer: null == employer
          ? _self.employer
          : employer // ignore: cast_nullable_to_non_nullable
              as EmployerSummaryDto,
    ));
  }

  /// Create a copy of FeedItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $MatchSummaryDtoCopyWith<$Res> get match {
    return $MatchSummaryDtoCopyWith<$Res>(_self.match, (value) {
      return _then(_self.copyWith(match: value));
    });
  }

  /// Create a copy of FeedItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $JobSummaryDtoCopyWith<$Res> get job {
    return $JobSummaryDtoCopyWith<$Res>(_self.job, (value) {
      return _then(_self.copyWith(job: value));
    });
  }

  /// Create a copy of FeedItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $EmployerSummaryDtoCopyWith<$Res> get employer {
    return $EmployerSummaryDtoCopyWith<$Res>(_self.employer, (value) {
      return _then(_self.copyWith(employer: value));
    });
  }
}

/// Adds pattern-matching-related methods to [FeedItemDto].
extension FeedItemDtoPatterns on FeedItemDto {
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
    TResult Function(_FeedItemDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _FeedItemDto() when $default != null:
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
    TResult Function(_FeedItemDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _FeedItemDto():
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
    TResult? Function(_FeedItemDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _FeedItemDto() when $default != null:
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
    TResult Function(MatchSummaryDto match, JobSummaryDto job,
            EmployerSummaryDto employer)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _FeedItemDto() when $default != null:
        return $default(_that.match, _that.job, _that.employer);
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
    TResult Function(MatchSummaryDto match, JobSummaryDto job,
            EmployerSummaryDto employer)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _FeedItemDto():
        return $default(_that.match, _that.job, _that.employer);
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
    TResult? Function(MatchSummaryDto match, JobSummaryDto job,
            EmployerSummaryDto employer)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _FeedItemDto() when $default != null:
        return $default(_that.match, _that.job, _that.employer);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _FeedItemDto implements FeedItemDto {
  const _FeedItemDto(
      {required this.match, required this.job, required this.employer});
  factory _FeedItemDto.fromJson(Map<String, dynamic> json) =>
      _$FeedItemDtoFromJson(json);

  @override
  final MatchSummaryDto match;
  @override
  final JobSummaryDto job;
  @override
  final EmployerSummaryDto employer;

  /// Create a copy of FeedItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$FeedItemDtoCopyWith<_FeedItemDto> get copyWith =>
      __$FeedItemDtoCopyWithImpl<_FeedItemDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$FeedItemDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _FeedItemDto &&
            (identical(other.match, match) || other.match == match) &&
            (identical(other.job, job) || other.job == job) &&
            (identical(other.employer, employer) ||
                other.employer == employer));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, match, job, employer);

  @override
  String toString() {
    return 'FeedItemDto(match: $match, job: $job, employer: $employer)';
  }
}

/// @nodoc
abstract mixin class _$FeedItemDtoCopyWith<$Res>
    implements $FeedItemDtoCopyWith<$Res> {
  factory _$FeedItemDtoCopyWith(
          _FeedItemDto value, $Res Function(_FeedItemDto) _then) =
      __$FeedItemDtoCopyWithImpl;
  @override
  @useResult
  $Res call(
      {MatchSummaryDto match, JobSummaryDto job, EmployerSummaryDto employer});

  @override
  $MatchSummaryDtoCopyWith<$Res> get match;
  @override
  $JobSummaryDtoCopyWith<$Res> get job;
  @override
  $EmployerSummaryDtoCopyWith<$Res> get employer;
}

/// @nodoc
class __$FeedItemDtoCopyWithImpl<$Res> implements _$FeedItemDtoCopyWith<$Res> {
  __$FeedItemDtoCopyWithImpl(this._self, this._then);

  final _FeedItemDto _self;
  final $Res Function(_FeedItemDto) _then;

  /// Create a copy of FeedItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? match = null,
    Object? job = null,
    Object? employer = null,
  }) {
    return _then(_FeedItemDto(
      match: null == match
          ? _self.match
          : match // ignore: cast_nullable_to_non_nullable
              as MatchSummaryDto,
      job: null == job
          ? _self.job
          : job // ignore: cast_nullable_to_non_nullable
              as JobSummaryDto,
      employer: null == employer
          ? _self.employer
          : employer // ignore: cast_nullable_to_non_nullable
              as EmployerSummaryDto,
    ));
  }

  /// Create a copy of FeedItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $MatchSummaryDtoCopyWith<$Res> get match {
    return $MatchSummaryDtoCopyWith<$Res>(_self.match, (value) {
      return _then(_self.copyWith(match: value));
    });
  }

  /// Create a copy of FeedItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $JobSummaryDtoCopyWith<$Res> get job {
    return $JobSummaryDtoCopyWith<$Res>(_self.job, (value) {
      return _then(_self.copyWith(job: value));
    });
  }

  /// Create a copy of FeedItemDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $EmployerSummaryDtoCopyWith<$Res> get employer {
    return $EmployerSummaryDtoCopyWith<$Res>(_self.employer, (value) {
      return _then(_self.copyWith(employer: value));
    });
  }
}

/// @nodoc
mixin _$MatchSummaryDto {
  String get id;
  double get totalScore;
  Map<String, dynamic> get scoreComponents;
  ExplanationDto? get explanation;
  DateTime? get surfacedAt;

  /// Create a copy of MatchSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $MatchSummaryDtoCopyWith<MatchSummaryDto> get copyWith =>
      _$MatchSummaryDtoCopyWithImpl<MatchSummaryDto>(
          this as MatchSummaryDto, _$identity);

  /// Serializes this MatchSummaryDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is MatchSummaryDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.totalScore, totalScore) ||
                other.totalScore == totalScore) &&
            const DeepCollectionEquality()
                .equals(other.scoreComponents, scoreComponents) &&
            (identical(other.explanation, explanation) ||
                other.explanation == explanation) &&
            (identical(other.surfacedAt, surfacedAt) ||
                other.surfacedAt == surfacedAt));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
      runtimeType,
      id,
      totalScore,
      const DeepCollectionEquality().hash(scoreComponents),
      explanation,
      surfacedAt);

  @override
  String toString() {
    return 'MatchSummaryDto(id: $id, totalScore: $totalScore, scoreComponents: $scoreComponents, explanation: $explanation, surfacedAt: $surfacedAt)';
  }
}

/// @nodoc
abstract mixin class $MatchSummaryDtoCopyWith<$Res> {
  factory $MatchSummaryDtoCopyWith(
          MatchSummaryDto value, $Res Function(MatchSummaryDto) _then) =
      _$MatchSummaryDtoCopyWithImpl;
  @useResult
  $Res call(
      {String id,
      double totalScore,
      Map<String, dynamic> scoreComponents,
      ExplanationDto? explanation,
      DateTime? surfacedAt});

  $ExplanationDtoCopyWith<$Res>? get explanation;
}

/// @nodoc
class _$MatchSummaryDtoCopyWithImpl<$Res>
    implements $MatchSummaryDtoCopyWith<$Res> {
  _$MatchSummaryDtoCopyWithImpl(this._self, this._then);

  final MatchSummaryDto _self;
  final $Res Function(MatchSummaryDto) _then;

  /// Create a copy of MatchSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? totalScore = null,
    Object? scoreComponents = null,
    Object? explanation = freezed,
    Object? surfacedAt = freezed,
  }) {
    return _then(_self.copyWith(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      totalScore: null == totalScore
          ? _self.totalScore
          : totalScore // ignore: cast_nullable_to_non_nullable
              as double,
      scoreComponents: null == scoreComponents
          ? _self.scoreComponents
          : scoreComponents // ignore: cast_nullable_to_non_nullable
              as Map<String, dynamic>,
      explanation: freezed == explanation
          ? _self.explanation
          : explanation // ignore: cast_nullable_to_non_nullable
              as ExplanationDto?,
      surfacedAt: freezed == surfacedAt
          ? _self.surfacedAt
          : surfacedAt // ignore: cast_nullable_to_non_nullable
              as DateTime?,
    ));
  }

  /// Create a copy of MatchSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $ExplanationDtoCopyWith<$Res>? get explanation {
    if (_self.explanation == null) {
      return null;
    }

    return $ExplanationDtoCopyWith<$Res>(_self.explanation!, (value) {
      return _then(_self.copyWith(explanation: value));
    });
  }
}

/// Adds pattern-matching-related methods to [MatchSummaryDto].
extension MatchSummaryDtoPatterns on MatchSummaryDto {
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
    TResult Function(_MatchSummaryDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _MatchSummaryDto() when $default != null:
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
    TResult Function(_MatchSummaryDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MatchSummaryDto():
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
    TResult? Function(_MatchSummaryDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MatchSummaryDto() when $default != null:
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
    TResult Function(
            String id,
            double totalScore,
            Map<String, dynamic> scoreComponents,
            ExplanationDto? explanation,
            DateTime? surfacedAt)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _MatchSummaryDto() when $default != null:
        return $default(_that.id, _that.totalScore, _that.scoreComponents,
            _that.explanation, _that.surfacedAt);
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
    TResult Function(
            String id,
            double totalScore,
            Map<String, dynamic> scoreComponents,
            ExplanationDto? explanation,
            DateTime? surfacedAt)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MatchSummaryDto():
        return $default(_that.id, _that.totalScore, _that.scoreComponents,
            _that.explanation, _that.surfacedAt);
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
    TResult? Function(
            String id,
            double totalScore,
            Map<String, dynamic> scoreComponents,
            ExplanationDto? explanation,
            DateTime? surfacedAt)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _MatchSummaryDto() when $default != null:
        return $default(_that.id, _that.totalScore, _that.scoreComponents,
            _that.explanation, _that.surfacedAt);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _MatchSummaryDto implements MatchSummaryDto {
  const _MatchSummaryDto(
      {required this.id,
      required this.totalScore,
      required final Map<String, dynamic> scoreComponents,
      this.explanation,
      this.surfacedAt})
      : _scoreComponents = scoreComponents;
  factory _MatchSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$MatchSummaryDtoFromJson(json);

  @override
  final String id;
  @override
  final double totalScore;
  final Map<String, dynamic> _scoreComponents;
  @override
  Map<String, dynamic> get scoreComponents {
    if (_scoreComponents is EqualUnmodifiableMapView) return _scoreComponents;
    // ignore: implicit_dynamic_type
    return EqualUnmodifiableMapView(_scoreComponents);
  }

  @override
  final ExplanationDto? explanation;
  @override
  final DateTime? surfacedAt;

  /// Create a copy of MatchSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$MatchSummaryDtoCopyWith<_MatchSummaryDto> get copyWith =>
      __$MatchSummaryDtoCopyWithImpl<_MatchSummaryDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$MatchSummaryDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _MatchSummaryDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.totalScore, totalScore) ||
                other.totalScore == totalScore) &&
            const DeepCollectionEquality()
                .equals(other._scoreComponents, _scoreComponents) &&
            (identical(other.explanation, explanation) ||
                other.explanation == explanation) &&
            (identical(other.surfacedAt, surfacedAt) ||
                other.surfacedAt == surfacedAt));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
      runtimeType,
      id,
      totalScore,
      const DeepCollectionEquality().hash(_scoreComponents),
      explanation,
      surfacedAt);

  @override
  String toString() {
    return 'MatchSummaryDto(id: $id, totalScore: $totalScore, scoreComponents: $scoreComponents, explanation: $explanation, surfacedAt: $surfacedAt)';
  }
}

/// @nodoc
abstract mixin class _$MatchSummaryDtoCopyWith<$Res>
    implements $MatchSummaryDtoCopyWith<$Res> {
  factory _$MatchSummaryDtoCopyWith(
          _MatchSummaryDto value, $Res Function(_MatchSummaryDto) _then) =
      __$MatchSummaryDtoCopyWithImpl;
  @override
  @useResult
  $Res call(
      {String id,
      double totalScore,
      Map<String, dynamic> scoreComponents,
      ExplanationDto? explanation,
      DateTime? surfacedAt});

  @override
  $ExplanationDtoCopyWith<$Res>? get explanation;
}

/// @nodoc
class __$MatchSummaryDtoCopyWithImpl<$Res>
    implements _$MatchSummaryDtoCopyWith<$Res> {
  __$MatchSummaryDtoCopyWithImpl(this._self, this._then);

  final _MatchSummaryDto _self;
  final $Res Function(_MatchSummaryDto) _then;

  /// Create a copy of MatchSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? id = null,
    Object? totalScore = null,
    Object? scoreComponents = null,
    Object? explanation = freezed,
    Object? surfacedAt = freezed,
  }) {
    return _then(_MatchSummaryDto(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      totalScore: null == totalScore
          ? _self.totalScore
          : totalScore // ignore: cast_nullable_to_non_nullable
              as double,
      scoreComponents: null == scoreComponents
          ? _self._scoreComponents
          : scoreComponents // ignore: cast_nullable_to_non_nullable
              as Map<String, dynamic>,
      explanation: freezed == explanation
          ? _self.explanation
          : explanation // ignore: cast_nullable_to_non_nullable
              as ExplanationDto?,
      surfacedAt: freezed == surfacedAt
          ? _self.surfacedAt
          : surfacedAt // ignore: cast_nullable_to_non_nullable
              as DateTime?,
    ));
  }

  /// Create a copy of MatchSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $ExplanationDtoCopyWith<$Res>? get explanation {
    if (_self.explanation == null) {
      return null;
    }

    return $ExplanationDtoCopyWith<$Res>(_self.explanation!, (value) {
      return _then(_self.copyWith(explanation: value));
    });
  }
}

/// @nodoc
mixin _$ExplanationDto {
  String get fit;
  String get generator;
  String get generatorVersion;
  String? get caveat;

  /// Create a copy of ExplanationDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $ExplanationDtoCopyWith<ExplanationDto> get copyWith =>
      _$ExplanationDtoCopyWithImpl<ExplanationDto>(
          this as ExplanationDto, _$identity);

  /// Serializes this ExplanationDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is ExplanationDto &&
            (identical(other.fit, fit) || other.fit == fit) &&
            (identical(other.generator, generator) ||
                other.generator == generator) &&
            (identical(other.generatorVersion, generatorVersion) ||
                other.generatorVersion == generatorVersion) &&
            (identical(other.caveat, caveat) || other.caveat == caveat));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, fit, generator, generatorVersion, caveat);

  @override
  String toString() {
    return 'ExplanationDto(fit: $fit, generator: $generator, generatorVersion: $generatorVersion, caveat: $caveat)';
  }
}

/// @nodoc
abstract mixin class $ExplanationDtoCopyWith<$Res> {
  factory $ExplanationDtoCopyWith(
          ExplanationDto value, $Res Function(ExplanationDto) _then) =
      _$ExplanationDtoCopyWithImpl;
  @useResult
  $Res call(
      {String fit, String generator, String generatorVersion, String? caveat});
}

/// @nodoc
class _$ExplanationDtoCopyWithImpl<$Res>
    implements $ExplanationDtoCopyWith<$Res> {
  _$ExplanationDtoCopyWithImpl(this._self, this._then);

  final ExplanationDto _self;
  final $Res Function(ExplanationDto) _then;

  /// Create a copy of ExplanationDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? fit = null,
    Object? generator = null,
    Object? generatorVersion = null,
    Object? caveat = freezed,
  }) {
    return _then(_self.copyWith(
      fit: null == fit
          ? _self.fit
          : fit // ignore: cast_nullable_to_non_nullable
              as String,
      generator: null == generator
          ? _self.generator
          : generator // ignore: cast_nullable_to_non_nullable
              as String,
      generatorVersion: null == generatorVersion
          ? _self.generatorVersion
          : generatorVersion // ignore: cast_nullable_to_non_nullable
              as String,
      caveat: freezed == caveat
          ? _self.caveat
          : caveat // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// Adds pattern-matching-related methods to [ExplanationDto].
extension ExplanationDtoPatterns on ExplanationDto {
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
    TResult Function(_ExplanationDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _ExplanationDto() when $default != null:
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
    TResult Function(_ExplanationDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ExplanationDto():
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
    TResult? Function(_ExplanationDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ExplanationDto() when $default != null:
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
    TResult Function(String fit, String generator, String generatorVersion,
            String? caveat)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _ExplanationDto() when $default != null:
        return $default(
            _that.fit, _that.generator, _that.generatorVersion, _that.caveat);
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
    TResult Function(String fit, String generator, String generatorVersion,
            String? caveat)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ExplanationDto():
        return $default(
            _that.fit, _that.generator, _that.generatorVersion, _that.caveat);
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
    TResult? Function(String fit, String generator, String generatorVersion,
            String? caveat)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _ExplanationDto() when $default != null:
        return $default(
            _that.fit, _that.generator, _that.generatorVersion, _that.caveat);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _ExplanationDto implements ExplanationDto {
  const _ExplanationDto(
      {required this.fit,
      required this.generator,
      required this.generatorVersion,
      this.caveat});
  factory _ExplanationDto.fromJson(Map<String, dynamic> json) =>
      _$ExplanationDtoFromJson(json);

  @override
  final String fit;
  @override
  final String generator;
  @override
  final String generatorVersion;
  @override
  final String? caveat;

  /// Create a copy of ExplanationDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$ExplanationDtoCopyWith<_ExplanationDto> get copyWith =>
      __$ExplanationDtoCopyWithImpl<_ExplanationDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$ExplanationDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _ExplanationDto &&
            (identical(other.fit, fit) || other.fit == fit) &&
            (identical(other.generator, generator) ||
                other.generator == generator) &&
            (identical(other.generatorVersion, generatorVersion) ||
                other.generatorVersion == generatorVersion) &&
            (identical(other.caveat, caveat) || other.caveat == caveat));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, fit, generator, generatorVersion, caveat);

  @override
  String toString() {
    return 'ExplanationDto(fit: $fit, generator: $generator, generatorVersion: $generatorVersion, caveat: $caveat)';
  }
}

/// @nodoc
abstract mixin class _$ExplanationDtoCopyWith<$Res>
    implements $ExplanationDtoCopyWith<$Res> {
  factory _$ExplanationDtoCopyWith(
          _ExplanationDto value, $Res Function(_ExplanationDto) _then) =
      __$ExplanationDtoCopyWithImpl;
  @override
  @useResult
  $Res call(
      {String fit, String generator, String generatorVersion, String? caveat});
}

/// @nodoc
class __$ExplanationDtoCopyWithImpl<$Res>
    implements _$ExplanationDtoCopyWith<$Res> {
  __$ExplanationDtoCopyWithImpl(this._self, this._then);

  final _ExplanationDto _self;
  final $Res Function(_ExplanationDto) _then;

  /// Create a copy of ExplanationDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? fit = null,
    Object? generator = null,
    Object? generatorVersion = null,
    Object? caveat = freezed,
  }) {
    return _then(_ExplanationDto(
      fit: null == fit
          ? _self.fit
          : fit // ignore: cast_nullable_to_non_nullable
              as String,
      generator: null == generator
          ? _self.generator
          : generator // ignore: cast_nullable_to_non_nullable
              as String,
      generatorVersion: null == generatorVersion
          ? _self.generatorVersion
          : generatorVersion // ignore: cast_nullable_to_non_nullable
              as String,
      caveat: freezed == caveat
          ? _self.caveat
          : caveat // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// @nodoc
mixin _$JobSummaryDto {
  String get id;
  String get title;
  String get location;
  String get status;
  DateTime get postedAt;
  String? get description;

  /// Create a copy of JobSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $JobSummaryDtoCopyWith<JobSummaryDto> get copyWith =>
      _$JobSummaryDtoCopyWithImpl<JobSummaryDto>(
          this as JobSummaryDto, _$identity);

  /// Serializes this JobSummaryDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is JobSummaryDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.title, title) || other.title == title) &&
            (identical(other.location, location) ||
                other.location == location) &&
            (identical(other.status, status) || other.status == status) &&
            (identical(other.postedAt, postedAt) ||
                other.postedAt == postedAt) &&
            (identical(other.description, description) ||
                other.description == description));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
      runtimeType, id, title, location, status, postedAt, description);

  @override
  String toString() {
    return 'JobSummaryDto(id: $id, title: $title, location: $location, status: $status, postedAt: $postedAt, description: $description)';
  }
}

/// @nodoc
abstract mixin class $JobSummaryDtoCopyWith<$Res> {
  factory $JobSummaryDtoCopyWith(
          JobSummaryDto value, $Res Function(JobSummaryDto) _then) =
      _$JobSummaryDtoCopyWithImpl;
  @useResult
  $Res call(
      {String id,
      String title,
      String location,
      String status,
      DateTime postedAt,
      String? description});
}

/// @nodoc
class _$JobSummaryDtoCopyWithImpl<$Res>
    implements $JobSummaryDtoCopyWith<$Res> {
  _$JobSummaryDtoCopyWithImpl(this._self, this._then);

  final JobSummaryDto _self;
  final $Res Function(JobSummaryDto) _then;

  /// Create a copy of JobSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? title = null,
    Object? location = null,
    Object? status = null,
    Object? postedAt = null,
    Object? description = freezed,
  }) {
    return _then(_self.copyWith(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      title: null == title
          ? _self.title
          : title // ignore: cast_nullable_to_non_nullable
              as String,
      location: null == location
          ? _self.location
          : location // ignore: cast_nullable_to_non_nullable
              as String,
      status: null == status
          ? _self.status
          : status // ignore: cast_nullable_to_non_nullable
              as String,
      postedAt: null == postedAt
          ? _self.postedAt
          : postedAt // ignore: cast_nullable_to_non_nullable
              as DateTime,
      description: freezed == description
          ? _self.description
          : description // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// Adds pattern-matching-related methods to [JobSummaryDto].
extension JobSummaryDtoPatterns on JobSummaryDto {
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
    TResult Function(_JobSummaryDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _JobSummaryDto() when $default != null:
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
    TResult Function(_JobSummaryDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _JobSummaryDto():
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
    TResult? Function(_JobSummaryDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _JobSummaryDto() when $default != null:
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
    TResult Function(String id, String title, String location, String status,
            DateTime postedAt, String? description)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _JobSummaryDto() when $default != null:
        return $default(_that.id, _that.title, _that.location, _that.status,
            _that.postedAt, _that.description);
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
    TResult Function(String id, String title, String location, String status,
            DateTime postedAt, String? description)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _JobSummaryDto():
        return $default(_that.id, _that.title, _that.location, _that.status,
            _that.postedAt, _that.description);
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
    TResult? Function(String id, String title, String location, String status,
            DateTime postedAt, String? description)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _JobSummaryDto() when $default != null:
        return $default(_that.id, _that.title, _that.location, _that.status,
            _that.postedAt, _that.description);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _JobSummaryDto implements JobSummaryDto {
  const _JobSummaryDto(
      {required this.id,
      required this.title,
      required this.location,
      required this.status,
      required this.postedAt,
      this.description});
  factory _JobSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$JobSummaryDtoFromJson(json);

  @override
  final String id;
  @override
  final String title;
  @override
  final String location;
  @override
  final String status;
  @override
  final DateTime postedAt;
  @override
  final String? description;

  /// Create a copy of JobSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$JobSummaryDtoCopyWith<_JobSummaryDto> get copyWith =>
      __$JobSummaryDtoCopyWithImpl<_JobSummaryDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$JobSummaryDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _JobSummaryDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.title, title) || other.title == title) &&
            (identical(other.location, location) ||
                other.location == location) &&
            (identical(other.status, status) || other.status == status) &&
            (identical(other.postedAt, postedAt) ||
                other.postedAt == postedAt) &&
            (identical(other.description, description) ||
                other.description == description));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(
      runtimeType, id, title, location, status, postedAt, description);

  @override
  String toString() {
    return 'JobSummaryDto(id: $id, title: $title, location: $location, status: $status, postedAt: $postedAt, description: $description)';
  }
}

/// @nodoc
abstract mixin class _$JobSummaryDtoCopyWith<$Res>
    implements $JobSummaryDtoCopyWith<$Res> {
  factory _$JobSummaryDtoCopyWith(
          _JobSummaryDto value, $Res Function(_JobSummaryDto) _then) =
      __$JobSummaryDtoCopyWithImpl;
  @override
  @useResult
  $Res call(
      {String id,
      String title,
      String location,
      String status,
      DateTime postedAt,
      String? description});
}

/// @nodoc
class __$JobSummaryDtoCopyWithImpl<$Res>
    implements _$JobSummaryDtoCopyWith<$Res> {
  __$JobSummaryDtoCopyWithImpl(this._self, this._then);

  final _JobSummaryDto _self;
  final $Res Function(_JobSummaryDto) _then;

  /// Create a copy of JobSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? id = null,
    Object? title = null,
    Object? location = null,
    Object? status = null,
    Object? postedAt = null,
    Object? description = freezed,
  }) {
    return _then(_JobSummaryDto(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      title: null == title
          ? _self.title
          : title // ignore: cast_nullable_to_non_nullable
              as String,
      location: null == location
          ? _self.location
          : location // ignore: cast_nullable_to_non_nullable
              as String,
      status: null == status
          ? _self.status
          : status // ignore: cast_nullable_to_non_nullable
              as String,
      postedAt: null == postedAt
          ? _self.postedAt
          : postedAt // ignore: cast_nullable_to_non_nullable
              as DateTime,
      description: freezed == description
          ? _self.description
          : description // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// @nodoc
mixin _$EmployerSummaryDto {
  String get id;
  String get name;
  DateTime? get verifiedAt;

  /// Create a copy of EmployerSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $EmployerSummaryDtoCopyWith<EmployerSummaryDto> get copyWith =>
      _$EmployerSummaryDtoCopyWithImpl<EmployerSummaryDto>(
          this as EmployerSummaryDto, _$identity);

  /// Serializes this EmployerSummaryDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is EmployerSummaryDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.name, name) || other.name == name) &&
            (identical(other.verifiedAt, verifiedAt) ||
                other.verifiedAt == verifiedAt));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, name, verifiedAt);

  @override
  String toString() {
    return 'EmployerSummaryDto(id: $id, name: $name, verifiedAt: $verifiedAt)';
  }
}

/// @nodoc
abstract mixin class $EmployerSummaryDtoCopyWith<$Res> {
  factory $EmployerSummaryDtoCopyWith(
          EmployerSummaryDto value, $Res Function(EmployerSummaryDto) _then) =
      _$EmployerSummaryDtoCopyWithImpl;
  @useResult
  $Res call({String id, String name, DateTime? verifiedAt});
}

/// @nodoc
class _$EmployerSummaryDtoCopyWithImpl<$Res>
    implements $EmployerSummaryDtoCopyWith<$Res> {
  _$EmployerSummaryDtoCopyWithImpl(this._self, this._then);

  final EmployerSummaryDto _self;
  final $Res Function(EmployerSummaryDto) _then;

  /// Create a copy of EmployerSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? name = null,
    Object? verifiedAt = freezed,
  }) {
    return _then(_self.copyWith(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      name: null == name
          ? _self.name
          : name // ignore: cast_nullable_to_non_nullable
              as String,
      verifiedAt: freezed == verifiedAt
          ? _self.verifiedAt
          : verifiedAt // ignore: cast_nullable_to_non_nullable
              as DateTime?,
    ));
  }
}

/// Adds pattern-matching-related methods to [EmployerSummaryDto].
extension EmployerSummaryDtoPatterns on EmployerSummaryDto {
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
    TResult Function(_EmployerSummaryDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _EmployerSummaryDto() when $default != null:
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
    TResult Function(_EmployerSummaryDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _EmployerSummaryDto():
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
    TResult? Function(_EmployerSummaryDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _EmployerSummaryDto() when $default != null:
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
    TResult Function(String id, String name, DateTime? verifiedAt)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _EmployerSummaryDto() when $default != null:
        return $default(_that.id, _that.name, _that.verifiedAt);
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
    TResult Function(String id, String name, DateTime? verifiedAt) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _EmployerSummaryDto():
        return $default(_that.id, _that.name, _that.verifiedAt);
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
    TResult? Function(String id, String name, DateTime? verifiedAt)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _EmployerSummaryDto() when $default != null:
        return $default(_that.id, _that.name, _that.verifiedAt);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _EmployerSummaryDto implements EmployerSummaryDto {
  const _EmployerSummaryDto(
      {required this.id, required this.name, this.verifiedAt});
  factory _EmployerSummaryDto.fromJson(Map<String, dynamic> json) =>
      _$EmployerSummaryDtoFromJson(json);

  @override
  final String id;
  @override
  final String name;
  @override
  final DateTime? verifiedAt;

  /// Create a copy of EmployerSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$EmployerSummaryDtoCopyWith<_EmployerSummaryDto> get copyWith =>
      __$EmployerSummaryDtoCopyWithImpl<_EmployerSummaryDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$EmployerSummaryDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _EmployerSummaryDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.name, name) || other.name == name) &&
            (identical(other.verifiedAt, verifiedAt) ||
                other.verifiedAt == verifiedAt));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, name, verifiedAt);

  @override
  String toString() {
    return 'EmployerSummaryDto(id: $id, name: $name, verifiedAt: $verifiedAt)';
  }
}

/// @nodoc
abstract mixin class _$EmployerSummaryDtoCopyWith<$Res>
    implements $EmployerSummaryDtoCopyWith<$Res> {
  factory _$EmployerSummaryDtoCopyWith(
          _EmployerSummaryDto value, $Res Function(_EmployerSummaryDto) _then) =
      __$EmployerSummaryDtoCopyWithImpl;
  @override
  @useResult
  $Res call({String id, String name, DateTime? verifiedAt});
}

/// @nodoc
class __$EmployerSummaryDtoCopyWithImpl<$Res>
    implements _$EmployerSummaryDtoCopyWith<$Res> {
  __$EmployerSummaryDtoCopyWithImpl(this._self, this._then);

  final _EmployerSummaryDto _self;
  final $Res Function(_EmployerSummaryDto) _then;

  /// Create a copy of EmployerSummaryDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? id = null,
    Object? name = null,
    Object? verifiedAt = freezed,
  }) {
    return _then(_EmployerSummaryDto(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      name: null == name
          ? _self.name
          : name // ignore: cast_nullable_to_non_nullable
              as String,
      verifiedAt: freezed == verifiedAt
          ? _self.verifiedAt
          : verifiedAt // ignore: cast_nullable_to_non_nullable
              as DateTime?,
    ));
  }
}

// dart format on
