# ca-demos-and-tools

## Getting started with Gerrit

First run `gcert` or `glogin`.

Next, run `git clone
sso://looker-internal/looker-open-source/ca-demos-and-tools`.

`cd ca-demos-and-tools` then run the following to install the commit hook that
assigns a change id to each commit.

```
f=`git rev-parse --git-dir`/hooks/commit-msg ; mkdir -p $(dirname $f) ; curl -Lo $f https://gerrit-review.googlesource.com/tools/hooks/commit-msg ; chmod +x $f
```

Changes are handled through Gerrit. The easiest way to work is to first create a
new branch. First make sure you are up to date with `git checkout main; git pull
--prune`. Then create the new branch with `git checkout -b my_feature_branch`.

Add and commit to that branch like normal. `git add FILE1 FILE2 ...`. `git
commit -m "commit message"`.

Now push that submit that change with `git push origin HEAD:refs/for/main`. You
will get back the URL with the change.

If tests don't pass or you need to update the change, checkout the branch again,
then amend the commit and push it. `git checkout my_feature_branch`, make
changes, `git add FILE1 FILE2 ...`. `git commit --amend`, `git push origin
HEAD:refs/for/main`.

When the change is submitted into main, checkout main locally and pull. `git
checkout main; git pull`. Delete the local branch. `git branch -D
my_feature_branch`.

If you accidentally commit to your local main, reset it with `git checkout main`
then `git reset --hard origin/main`. That will reset your main branch in a way
that your changes are "lost". So use that command after your changes have been
submitted into main. Alternately you can go back before the change was commited
but keep the local copy of your changes with `git reset --soft HEAD~1`. Then
you can create a new feature branch and commit your changes there.
