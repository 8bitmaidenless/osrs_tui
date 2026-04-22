# Changelog

<!--next-version-placeholder-->

## v0.1.0 (21/04/2026)

- First release of `osrs_tui`!

## v0.2.0

- Skill Calculator screen now implemented and live

### v0.2.1

+ UI Fix:
    - Two sync would recursively update it's corresponding input field (e.g., start-xp <-> start-lvl)
    - In **v0.2.0**, this was mitigated by updating the event callback method to happen on Input submission (rather than Input changing), meaning the user had to press the Enter key before seeing the other field reflect the one currently being edited. 
    - This has now been fixed via the `.prevent()` method on Input widgets, allowing us to silence the event whenever we don't want a field to call the callback method. The event method now happens on Input.Changed.

