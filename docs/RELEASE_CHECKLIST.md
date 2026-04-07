# RELEASE CHECKLIST

Use this checklist whenever publishing a new version of VARA Term.

------------------------------------------------------------------------

## 1. Prepare the Update

☐ Ensure all intended improvements and bug fixes are complete\
☐ Test the application locally\
☐ Verify the GUI works at normal window sizes\
☐ Confirm no obvious regressions

------------------------------------------------------------------------

## 2. Update Version Number

☐ Update `version.txt`\
☐ Follow Semantic Versioning:

MAJOR.MINOR.PATCH

Examples:

1.0.1 -- Bug fixes\
1.1.0 -- New features\
2.0.0 -- Major changes

------------------------------------------------------------------------

## 3. Update Documentation

☐ Add new entry to `CHANGELOG.md`\
☐ Update README if new features were added

Example:

Version 1.0.3

-   Improved settings GUI
-   Fixed scrolling issue
-   Added diagnostics tab

------------------------------------------------------------------------

## 4. Commit Changes (GitHub Desktop)

Open GitHub Desktop and:

☐ Review changed files\
☐ Add commit summary (example: "Prepare release 1.0.3")\
☐ Commit to main\
☐ Push to origin

------------------------------------------------------------------------

## 5. Create GitHub Release

On GitHub:

☐ Open repository\
☐ Click **Releases**\
☐ Click **Create new release**

Fill in:

Tag version: `vX.Y.Z`\
Release title: `VARA Term X.Y.Z`

------------------------------------------------------------------------

## 6. Upload Release Files

Attach:

☐ Windows executable (`vterm.exe`)\
☐ Source code archive (optional)

------------------------------------------------------------------------

## 7. Publish Release

☐ Click **Publish Release**

Users can now download the new version.

------------------------------------------------------------------------

## 8. Post‑Release Verification

☐ Download the release from GitHub\
☐ Confirm executable runs correctly\
☐ Verify version number appears correctly in the app

------------------------------------------------------------------------

Release complete.
