-- List operations and properties

theorem listAppendNil (xs : List α) : xs ++ [] = xs := by
  rw [List.append_nil]

theorem listLengthAppend (xs ys : List α) :
  (xs ++ ys).length = xs.length + ys.length := by
  rw [List.length_append]

theorem listReverseReverse (xs : List α) : xs.reverse.reverse = xs := by
  rw [List.reverse_reverse]

theorem emptyListLength : ([] : List α).length = 0 := by
  rfl

theorem consLengthSucc (x : α) (xs : List α) :
  (x :: xs).length = xs.length + 1 := by
  rfl
