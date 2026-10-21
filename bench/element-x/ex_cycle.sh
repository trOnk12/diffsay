#!/bin/bash
set -u
EX=${EX:-$PWD/element-x-android}
export ANDROID_HOME=/opt/android-sdk JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
G="timeout 7000 bash ./gradlew --console=plain --max-workers=2 -Pkotlin.compiler.execution.strategy=in-process -Dorg.gradle.jvmargs=-Xmx6g"
clean_jvms() { (cd $EX && bash ./gradlew --stop -q >/dev/null 2>&1); for p in $(ps -eo pid,args | awk '/[G]radleWorkerMain|[K]otlinCompileDaemon/{print $1}'); do kill $p 2>/dev/null; done; sleep 3; }
phase() {  # $1 = gradle task, $2 = log; retries once if the daemon dies
  for attempt in 1 2; do
    clean_jvms
    (cd $EX && $G :tests:uitests:$1 --tests "ui.PreviewShard*" > $2 2>&1); echo "rc=$? attempt=$attempt" >> $2
    grep -q "daemon disappeared\|disappeared unexpectedly" $2 || break
  done
}
cd $EX
echo "== before" ; git stash -q -u 2>/dev/null; git checkout -q -f; GIT_LFS_SKIP_SMUDGE=1 git checkout -q -f 37fed3e8fe6776ad8097cff5d43c0442d77a17f2
rm -rf tests/uitests/src/test/snapshots/images/*.slots.json.gz
python3 $(dirname $0)/ex_patch.py
phase recordPaparazziDebug before.log
rm -rf $EX/../before-snapshots && cp -r tests/uitests/src/test/snapshots $EX/../before-snapshots
echo "before dumps: $(ls $EX/../before-snapshots/images | grep -c slots)"
echo "== after"; git stash -q -u 2>/dev/null; git checkout -q -f; GIT_LFS_SKIP_SMUDGE=1 git checkout -q -f f0a6cba6dbbd8113108a012ef93b92989079997b
rm -rf tests/uitests/src/test/snapshots && cp -r $EX/../before-snapshots tests/uitests/src/test/snapshots
python3 $(dirname $0)/ex_patch.py
rm -rf tests/uitests/build/paparazzi
phase verifyPaparazziDebug after.log
echo "deltas: $(ls tests/uitests/build/paparazzi/failures/debug | grep -c delta)"
cd /tmp && timeout 1800 diffsay scan $EX/tests/uitests/build --source $EX > scan.txt 2>&1
echo DONE
