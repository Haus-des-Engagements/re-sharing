## 1. Amount of zero (red, then green)

- [x] 1.1 Add tests: the import accepts zero and an empty amount and refuses a negative one, also for a kind with a minimum amount; `Agreement.clean` accepts zero and refuses negative amounts; manager forms accept zero and refuse negative amounts; applicants are refused zero
- [x] 1.2 Add tests: an active agreement with amount zero gets no due collections and no first-period collection
- [x] 1.3 Implement the model, import, form and collection changes
- [x] 1.4 Name the option in the manager guide's import table; add the German translation
- [x] 1.5 Run the agreement tests and pre-commit on the changed files
