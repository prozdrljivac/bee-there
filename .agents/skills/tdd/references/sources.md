# TDD research sources

These references support the workflow in this skill.

- Kent Beck, **Canon TDD**: keep a behavior list, turn one item at a time into a test, make all tests pass, then optionally refactor. Do not make the whole list executable before implementation.  
  https://newsletter.kentbeck.com/p/canon-tdd

- Martin Fowler, **Test Driven Development**: describes the Red-Green-Refactor cycle and the importance of the refactor step.  
  https://martinfowler.com/bliki/TestDrivenDevelopment.html

- Kent Beck, **Test Desiderata**: tests should be isolated, deterministic, fast, behavioral, and insensitive to internal structure.  
  https://testdesiderata.com/

- Google, **Software Engineering at Google — Unit Testing**: test behavior through public APIs, avoid implementation-detail coupling, and add regression coverage for bugs.  
  https://abseil.io/resources/swe-book/html/ch12.html

- Google, **Software Engineering at Google — Testing Overview**: distinguishes test size from scope and explains the value of fast, deterministic small tests.  
  https://abseil.io/resources/swe-book/html/ch11.html

- Google, **Software Engineering at Google — Larger Testing**: explains why integration and system tests are needed in addition to unit tests and describes their fidelity and reliability tradeoffs.  
  https://abseil.io/resources/swe-book/html/ch14.html

- Google, **Software Engineering at Google — Test Doubles**: prefer real dependencies when practical; use doubles for difficult boundaries; avoid brittle interaction testing; verify reusable fakes against real implementations.  
  https://abseil.io/resources/swe-book/html/ch13.html

- Martin Fowler, **Mocks Aren't Stubs**: distinguishes test-double styles and their design tradeoffs.  
  https://martinfowler.com/articles/mocksArentStubs.html

- Martin Fowler, **Refactoring**: refactoring preserves observable behavior and proceeds through small, tested changes.  
  https://refactoring.com/

- Martin Fowler, **Legacy Seam**: seams help bring difficult existing code under test by providing places where dependencies can be substituted.  
  https://martinfowler.com/bliki/LegacySeam.html

- Michael Feathers, **Working Effectively with Legacy Code**: techniques for bringing untested code under control while preserving behavior.  
  https://www.informit.com/store/working-effectively-with-legacy-code-9780131177055
