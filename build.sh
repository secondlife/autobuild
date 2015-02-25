#!/bin/bash

echo_service_message()
{
  sleep 0.1
  echo "##teamcity[$@]" 1>&2
}

record_event()
{
  local message=$(echo "$1" | sed -e "s/|/||/g; s/'/|'/g")
  echo_service_message message text="'${message}'"
}

begin_section()
{
  echo_service_message blockOpened name="'$1'"
}

end_section()
{
  echo_service_message blockClosed name="'$1'"
}

set -e
case "$arch" in
    CYGWIN)
        # this ensures we use the Windows Python
        nosetests="nosetests.exe"
        ;;
    *)
        nosetests="nosetests"
        ;;
esac

begin_section "Self Test"

# ensure AUTOBUILD is in native path form for child processes
export AUTOBUILD="$(native_path "$AUTOBUILD")"

if $nosetests -v
then
    echo_service_message buildStatus text="'Self Test Passed'" status="'SUCCESS'"
    ExitStatus=0
else
    echo_service_message buildStatus text="'Self Test Failed'" status="'FAILURE'"
    ExitStatus=1
fi
end_section "Self Test"

exit $ExitStatus
